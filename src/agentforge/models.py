"""Relational source of truth. JSON is limited to bounded payloads/snapshots."""

import time
import uuid
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class APIKey(Base):
    """An owner (workspace). The historical table name predates multiple credentials.

    For deployments created before credentials existed, the id is the SHA-256 of the
    original operator key; it is now only an identifier and survives key rotation.
    """

    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), default="operator")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Credential(Base):
    """A bearer key for an owner. Only the SHA-256 of the key is stored."""

    __tablename__ = "credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16))
    bootstrap: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    expires_at: Mapped[float | None] = mapped_column(Float)
    revoked_at: Mapped[float | None] = mapped_column(Float)
    revoked_by: Mapped[str | None] = mapped_column(String(36))
    last_used_at: Mapped[float | None] = mapped_column(Float)


class WorkerHeartbeat(Base):
    """Liveness and capability report written by each worker process."""

    __tablename__ = "worker_heartbeats"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    started_at: Mapped[float] = mapped_column(Float)
    seen_at: Mapped[float] = mapped_column(Float, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36))
    sandbox_ready: Mapped[bool] = mapped_column(default=False)
    providers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class AgentRow(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    __table_args__ = (UniqueConstraint("owner_id", "name", "version"),)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    task: Mapped[str] = mapped_column(Text)
    fixture: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)
    deadline: Mapped[float] = mapped_column(Float)
    available_at: Mapped[float] = mapped_column(Float, default=time.time)
    lease_until: Mapped[float | None] = mapped_column(Float)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    recoveries: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    checkpoint_seq: Mapped[int] = mapped_column(Integer, default=0)
    spent_microusd: Mapped[int] = mapped_column(Integer, default=0)
    charged_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str | None] = mapped_column(String(64))
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key"),
        Index("ix_runs_claim", "status", "available_at", "lease_until"),
        Index("ix_runs_owner_created", "owner_id", "created_at"),
    )


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)


class Step(Base):
    __tablename__ = "run_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default="STARTED")
    provider: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(80))
    routing_reason: Mapped[str | None] = mapped_column(String(160))
    cost_microusd: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[float] = mapped_column(Float, default=time.time)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_type: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("run_id", "sequence", "attempt"),)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    kind: Mapped[str] = mapped_column(String(64))
    at: Mapped[float] = mapped_column(Float, default=time.time)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (Index("ix_events_run_cursor", "run_id", "id"),)
