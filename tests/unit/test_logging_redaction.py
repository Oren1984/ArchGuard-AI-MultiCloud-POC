from __future__ import annotations

from app.core.logging import RedactingJsonFormatter


def test_redacting_formatter_masks_known_secret_keys():
    formatter = RedactingJsonFormatter()
    record = {
        "message": "connecting",
        "password": "super-secret",
        "api_key": "sk-12345",
        "token": "abcdef",
        "Authorization": "Bearer xyz",
        "safe_field": "keep-me",
    }
    processed = formatter.process_log_record(dict(record))
    assert processed["password"] == "***REDACTED***"
    assert processed["api_key"] == "***REDACTED***"
    assert processed["token"] == "***REDACTED***"
    assert processed["Authorization"] == "***REDACTED***"
    assert processed["safe_field"] == "keep-me"
