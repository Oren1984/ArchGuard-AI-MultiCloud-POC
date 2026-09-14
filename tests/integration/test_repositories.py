"""Repository/database tests against a real PostgreSQL instance (never
SQLite) — persistence, constraints, cascades, and hash-chained audit
integrity."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import models
from app.repositories.postgres_repositories import (
    SqlAlchemyAuditRepository,
    SqlAlchemyEventRepository,
    SqlAlchemyRecommendationRepository,
    SqlAlchemyRiskAssessmentRepository,
)

pytestmark = pytest.mark.integration


def _make_event(**overrides) -> models.OperationalEvent:
    defaults = dict(
        event_type="performance_degradation",
        source="datadog",
        description="desc",
        affected_service="svc",
        environment="development",
        severity="low",
        status="open",
        evidence=["obs-1"],
    )
    defaults.update(overrides)
    return models.OperationalEvent(**defaults)


def test_event_create_and_get_round_trip(db_session):
    repo = SqlAlchemyEventRepository(db_session)
    created = repo.create(_make_event())
    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.affected_service == "svc"


def test_event_get_returns_none_for_unknown_id(db_session):
    repo = SqlAlchemyEventRepository(db_session)
    assert repo.get(uuid.uuid4()) is None


def test_event_list_filters_by_status_and_environment(db_session):
    repo = SqlAlchemyEventRepository(db_session)
    repo.create(_make_event(status="open", environment="production"))
    repo.create(_make_event(status="blocked", environment="production"))
    repo.create(_make_event(status="open", environment="staging"))

    from app.domain.enums import EventStatus

    open_prod = repo.list(limit=50, offset=0, status=EventStatus.OPEN, environment="production")
    assert len(open_prod) == 1
    assert open_prod[0].status == "open"
    assert open_prod[0].environment == "production"


def test_risk_assessment_score_check_constraint_rejects_out_of_range(db_session):
    repo = SqlAlchemyEventRepository(db_session)
    event = repo.create(_make_event())
    risk_repo = SqlAlchemyRiskAssessmentRepository(db_session)

    bad_assessment = models.RiskAssessment(
        event_id=event.id,
        score=150,
        level="critical",
        triggered_rules=[],
        explanation="x",
        engine_version="v1",
    )
    with pytest.raises(IntegrityError):
        risk_repo.create(bad_assessment)


def test_ai_recommendation_confidence_check_constraint_rejects_out_of_range(db_session):
    event_repo = SqlAlchemyEventRepository(db_session)
    risk_repo = SqlAlchemyRiskAssessmentRepository(db_session)
    event = event_repo.create(_make_event())
    assessment = risk_repo.create(
        models.RiskAssessment(
            event_id=event.id, score=10, level="low", triggered_rules=[], explanation="x", engine_version="v1"
        )
    )

    rec_repo = SqlAlchemyRecommendationRepository(db_session)
    bad_rec = models.AIRecommendation(
        event_id=event.id,
        risk_assessment_id=assessment.id,
        provider="mock",
        model_name="m",
        prompt_version="v1",
        input_reference={},
        summary="s",
        suggested_response="r",
        evidence_references=[],
        confidence=1.5,
        proposed_action="notify_only",
        raw_output={},
    )
    with pytest.raises(IntegrityError):
        rec_repo.create(bad_rec)


def test_cascade_delete_event_removes_risk_assessments(db_session):
    event_repo = SqlAlchemyEventRepository(db_session)
    risk_repo = SqlAlchemyRiskAssessmentRepository(db_session)
    event = event_repo.create(_make_event())
    risk_repo.create(
        models.RiskAssessment(
            event_id=event.id, score=10, level="low", triggered_rules=[], explanation="x", engine_version="v1"
        )
    )
    db_session.flush()

    db_session.delete(event)
    db_session.flush()

    assert risk_repo.get_latest_for_event(event.id) is None


def test_audit_hash_chain_is_valid_after_multiple_appends(db_session):
    audit_repo = SqlAlchemyAuditRepository(db_session)
    audit_repo.append(actor="system", action="event_created", details={"a": 1})
    audit_repo.append(actor="system", action="risk_assessed", details={"b": 2})
    audit_repo.append(actor="approver:jane", action="approval_granted", details={"c": 3})

    assert audit_repo.verify_chain() is True


def test_audit_hash_chain_detects_tampering(db_session):
    audit_repo = SqlAlchemyAuditRepository(db_session)
    audit_repo.append(actor="system", action="event_created", details={"a": 1})
    entry = audit_repo.append(actor="system", action="risk_assessed", details={"b": 2})

    entry.details = {"b": "tampered"}
    db_session.flush()

    assert audit_repo.verify_chain() is False


def test_audit_entries_ordered_by_sequence(db_session):
    audit_repo = SqlAlchemyAuditRepository(db_session)
    event_repo = SqlAlchemyEventRepository(db_session)
    event = event_repo.create(_make_event())

    audit_repo.append(actor="system", action="event_created", details={}, event_id=event.id)
    audit_repo.append(actor="system", action="risk_assessed", details={}, event_id=event.id)

    entries = audit_repo.list_for_event(event.id)
    assert [e.action for e in entries] == ["event_created", "risk_assessed"]
    assert entries[0].seq < entries[1].seq


def test_transaction_rollback_discards_uncommitted_writes(db_session):
    event_repo = SqlAlchemyEventRepository(db_session)
    savepoint = db_session.begin_nested()
    created = event_repo.create(_make_event(source="rollback-test"))
    created_id = created.id
    savepoint.rollback()

    assert event_repo.get(created_id) is None
