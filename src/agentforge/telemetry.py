"""Allowlisted structured logs: no prompts, tool output, headers, or exception messages."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter("agentforge_http_requests_total", "HTTP requests", ["method", "status"])
LATENCY = Histogram("agentforge_http_duration_seconds", "HTTP request duration")

# Database-derived gauges, refreshed on each scrape so every API replica reports the same
# queue truth rather than its own process-local counters.
RUNS = Gauge("agentforge_runs", "Runs by current status", ["status"])
OLDEST_QUEUED = Gauge("agentforge_oldest_queued_age_seconds", "Age of the oldest queued run")
EXPIRED_LEASES = Gauge(
    "agentforge_expired_lease_runs", "RUNNING runs whose lease expired (awaiting recovery)"
)
WORKER_AGE = Gauge(
    "agentforge_worker_heartbeat_age_seconds", "Seconds since any worker heartbeat (-1: never)"
)
SPEND_TODAY = Gauge(
    "agentforge_spend_today_microusd", "Estimated spend of runs created this UTC day"
)
STEPS_HOUR = Gauge(
    "agentforge_steps_last_hour", "Steps started in the last hour", ["kind", "status"]
)
STATUSES = ("QUEUED", "RUNNING", "RETRYING", "COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT")

# Non-secret identifiers and measurements only. `actor`/`credential_id` are credential UUIDs.
ALLOWED_FIELDS = frozenset(
    {
        "request_id",
        "run_id",
        "duration_ms",
        "error_type",
        "status",
        "step_id",
        "method",
        "route",
        "actor",
        "credential_id",
        "worker_id",
    }
)


def log(service: str, event: str, **fields: Any) -> None:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "INFO",
        "service": service,
        "event": event,
    }
    record.update({key: value for key, value in fields.items() if key in ALLOWED_FIELDS})
    logging.getLogger("agentforge").info(json.dumps(record))


def publish_snapshot(snapshot: dict[str, Any]) -> None:
    for status in STATUSES:
        RUNS.labels(status).set(snapshot["runs_by_status"].get(status, 0))
    OLDEST_QUEUED.set(snapshot["oldest_queued_age_seconds"])
    EXPIRED_LEASES.set(snapshot["expired_lease_runs"])
    age = snapshot["worker_heartbeat_age_seconds"]
    WORKER_AGE.set(-1 if age is None else age)
    SPEND_TODAY.set(snapshot["spend_today_microusd"])
    STEPS_HOUR.clear()
    for kind, status, count in snapshot["steps_last_hour"]:
        STEPS_HOUR.labels(kind, status).set(count)
