"""Structured JSON logging with correlation-ID propagation.

Never log secrets: config values that could contain credentials (API keys,
DB passwords, connection strings) must never be passed to these loggers.
"""

from __future__ import annotations

import contextvars
import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

_REDACT_KEYS = {"password", "api_key", "secret", "token", "authorization"}


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


class RedactingJsonFormatter(jsonlogger.JsonFormatter):
    def process_log_record(self, log_record: dict[str, Any]) -> dict[str, Any]:
        for key in list(log_record.keys()):
            if key.lower() in _REDACT_KEYS:
                log_record[key] = "***REDACTED***"
        return super().process_log_record(log_record)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = RedactingJsonFormatter("%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s")
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
