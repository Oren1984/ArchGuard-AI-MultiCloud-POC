from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

ACTOR = {"X-ArchGuard-Actor": "operator:test"}


def test_regression_evaluation_run_returns_eligible_for_mock_provider(client):
    resp = client.post("/providers/regression-evaluation", json={}, headers=ACTOR)
    assert resp.status_code == 201
    body = resp.json()
    assert body["provider"] == "mock"
    assert body["eligible"] is True
    assert body["pass_rate"] == 1.0
    assert body["dataset_version"] == "regression-v1"


def test_eligibility_lookup_returns_404_before_any_run(client):
    resp = client.get("/providers/eligibility")
    assert resp.status_code == 404


def test_eligibility_lookup_returns_latest_record_after_run(client):
    client.post("/providers/regression-evaluation", json={}, headers=ACTOR)
    resp = client.get("/providers/eligibility")
    assert resp.status_code == 200
    assert resp.json()["eligible"] is True
