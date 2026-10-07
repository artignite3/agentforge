"""Allowlisted structured logs: no prompts, tool output, headers, or exception messages."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter, Histogram

REQUESTS = Counter("agentforge_http_requests_total", "HTTP requests", ["method", "status"])
LATENCY = Histogram("agentforge_http_duration_seconds", "HTTP request duration")


def log(service: str, event: str, **fields: Any) -> None:
    allowed = {"request_id", "run_id", "duration_ms", "error_type", "status", "step_id"}
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "INFO",
        "service": service,
        "event": event,
    }
    record.update({key: value for key, value in fields.items() if key in allowed})
    logging.getLogger("agentforge").info(json.dumps(record))
