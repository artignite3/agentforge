"""Transactional queue, fenced leases, and atomic checkpoint/event commits."""

import hashlib
import json
import time
from typing import Any

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agentforge.config import Settings
from agentforge.domain import TERMINAL, Agent, RunCreate, Status, transition
from agentforge.fixtures import repository
from agentforge.models import (
    AgentRow,
    APIKey,
    Base,
    Checkpoint,
    Credential,
    Event,
    Run,
    Step,
    WorkerHeartbeat,
    uid,
)
from agentforge.security import ROLE_RANK, Principal, generate_key, key_hash


class StoreError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


class LeaseLost(Exception):
    """The caller may no longer commit results or start external work."""


# Internal coordination fields: useful to the store, meaningless or sensitive to API clients.
PRIVATE_FIELDS = frozenset({"lease_token", "request_hash", "owner_id", "key_hash"})
DAY_SECONDS = 86400


def as_dict(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def public(row: Any) -> dict[str, Any]:
    return {k: v for k, v in as_dict(row).items() if k not in PRIVATE_FIELDS}


def event(session: AsyncSession, run: Run, kind: str, **data: Any) -> None:
    run.updated_at = time.time()
    session.add(Event(run_id=run.id, kind=kind, data=data))


def set_status(session: AsyncSession, run: Run, status: Status, **data: Any) -> None:
    transition(run.status, status)
    run.status = status.value
    event(session, run, "run." + status.value.lower(), **data)
    if status in TERMINAL:
        run.lease_token = None
        run.lease_until = None


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def _close_started(self, session: AsyncSession, run: Run, status: Status) -> None:
        steps = await session.scalars(
            select(Step).where(Step.run_id == run.id, Step.status == "STARTED")
        )
        for step in steps:
            step.status = status.value
            step.error_type = status.value

    async def create_schema(self) -> None:
        """Test/local helper; production startup uses Alembic migrations."""
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def ready(self) -> None:
        async with self.sessions() as session:
            await session.execute(text("SELECT 1"))
            await session.execute(select(Run.id).limit(1))

    async def bootstrap_credential(self, key: str) -> str:
        """Ensure the operator key from the environment is an admin credential.

        First start: create the owner (id = hash of this key, matching earlier releases)
        with an admin bootstrap credential. A later start with a *different* key on a
        single-owner deployment is a rotation: the new key joins the same owner and the
        previous bootstrap credential is revoked, so no agents or runs are orphaned.
        Returns the owner id.
        """
        digest = key_hash(key)
        async with self.sessions.begin() as session:
            existing = await session.scalar(select(Credential).where(Credential.key_hash == digest))
            if existing is not None:
                return existing.owner_id
            owners = list(await session.scalars(select(APIKey.id).limit(2)))
            if len(owners) > 1:
                raise StoreError("Multiple owners exist; attach the bootstrap key explicitly")
            owner = owners[0] if owners else digest
            if not owners:
                session.add(APIKey(id=owner))
                await session.flush()
            await session.execute(
                update(Credential)
                .where(
                    Credential.owner_id == owner,
                    Credential.bootstrap.is_(True),
                    Credential.revoked_at.is_(None),
                )
                .values(revoked_at=time.time(), revoked_by="bootstrap-rotation")
            )
            session.add(
                Credential(
                    owner_id=owner, key_hash=digest, label="bootstrap", role="admin", bootstrap=True
                )
            )
            return owner

    async def principal(self, digest: str) -> Principal | None:
        async with self.sessions.begin() as session:
            row = await session.scalar(select(Credential).where(Credential.key_hash == digest))
            now = time.time()
            if row is None or row.revoked_at is not None:
                return None
            if row.expires_at is not None and row.expires_at <= now:
                return None
            if row.last_used_at is None or row.last_used_at < now - 60:
                row.last_used_at = now  # Throttled: at most one write per key per minute.
            return Principal(row.owner_id, row.id, row.label, row.role, row.expires_at)

    async def create_credential(
        self,
        owner: str,
        label: str,
        role: str,
        expires_at: float | None = None,
        created_by: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Returns the public record and the plaintext key, which is never stored."""
        if role not in ROLE_RANK:
            raise StoreError("Unknown role", 422)
        if expires_at is not None and expires_at <= time.time():
            raise StoreError("Expiry must be in the future", 422)
        key = generate_key()
        async with self.sessions.begin() as session:
            row = Credential(
                owner_id=owner,
                key_hash=key_hash(key),
                label=label,
                role=role,
                expires_at=expires_at,
                created_by=created_by,
            )
            session.add(row)
            await session.flush()
            return public(row), key

    async def list_credentials(self, owner: str) -> list[dict[str, Any]]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(Credential)
                .where(Credential.owner_id == owner)
                .order_by(Credential.created_at.desc())
                .limit(200)
            )
            return [public(row) for row in rows]

    async def revoke_credential(
        self, owner: str, credential_id: str, revoked_by: str | None = None
    ) -> dict[str, Any]:
        async with self.sessions.begin() as session:
            row = await session.scalar(
                select(Credential)
                .where(Credential.id == credential_id, Credential.owner_id == owner)
                .with_for_update()
            )
            if row is None:
                raise StoreError("Key not found", 404)
            if row.bootstrap:
                raise StoreError("Rotate the bootstrap key through the environment instead")
            if row.revoked_at is None:
                row.revoked_at = time.time()
                row.revoked_by = revoked_by
            return public(row)

    async def record_worker(
        self,
        worker_id: str,
        started_at: float,
        run_id: str | None,
        sandbox_ready: bool,
        providers: list[dict[str, Any]],
    ) -> None:
        now = time.time()
        async with self.sessions.begin() as session:
            row = await session.get(WorkerHeartbeat, worker_id)
            if row is None:
                row = WorkerHeartbeat(id=worker_id, started_at=started_at)
                session.add(row)
            row.seen_at, row.run_id = now, run_id
            row.sandbox_ready, row.providers = sandbox_ready, providers
            await session.execute(
                delete(WorkerHeartbeat).where(WorkerHeartbeat.seen_at < now - DAY_SECONDS)
            )

    async def workers(self, fresh_seconds: float = 30) -> list[dict[str, Any]]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(WorkerHeartbeat)
                .where(WorkerHeartbeat.seen_at >= time.time() - fresh_seconds)
                .order_by(WorkerHeartbeat.seen_at.desc())
            )
            return [as_dict(row) for row in rows]

    async def metrics_snapshot(self) -> dict[str, Any]:
        """Queue, worker, and spend gauges for the Prometheus endpoint (all owners)."""
        now = time.time()
        async with self.sessions() as session:
            statuses = {
                status: count
                for status, count in (
                    await session.execute(select(Run.status, func.count()).group_by(Run.status))
                ).all()
            }
            oldest = await session.scalar(
                select(func.min(Run.created_at)).where(Run.status == "QUEUED")
            )
            stale = await session.scalar(
                select(func.count())
                .select_from(Run)
                .where(
                    Run.status == "RUNNING", or_(Run.lease_until.is_(None), Run.lease_until < now)
                )
            )
            seen = await session.scalar(select(func.max(WorkerHeartbeat.seen_at)))
            spent = await session.scalar(
                select(func.coalesce(func.sum(Run.spent_microusd), 0)).where(
                    Run.created_at >= now - now % DAY_SECONDS
                )
            )
            steps = (
                await session.execute(
                    select(Step.kind, Step.status, func.count())
                    .where(Step.started_at >= now - 3600)
                    .group_by(Step.kind, Step.status)
                )
            ).all()
        return {
            "runs_by_status": statuses,
            "oldest_queued_age_seconds": now - oldest if oldest else 0.0,
            "expired_lease_runs": stale or 0,
            "worker_heartbeat_age_seconds": now - seen if seen else None,
            "spend_today_microusd": spent or 0,
            "steps_last_hour": [(kind, status, count) for kind, status, count in steps],
        }

    async def prune(
        self, checkpoint_days: float, run_days: float | None = None, dry_run: bool = False
    ) -> dict[str, int]:
        """Retention for terminal runs. Queued, running, and retrying work is never touched.

        - Intermediate checkpoints of terminal runs last updated more than `checkpoint_days`
          ago are deleted; the latest checkpoint (the trace's final source) is kept.
        - With `run_days`, whole terminal runs older than that are deleted with their steps,
          checkpoints, and events. Children keep their history; their parent link is cleared.
        """
        now = time.time()
        terminal = [s.value for s in TERMINAL]
        counts = {"checkpoints": 0, "runs": 0}
        async with self.sessions.begin() as session:
            old_runs = select(Run.id).where(
                Run.status.in_(terminal), Run.updated_at < now - checkpoint_days * DAY_SECONDS
            )
            latest = select(Run.checkpoint_seq).where(Run.id == Checkpoint.run_id).scalar_subquery()
            condition = (Checkpoint.run_id.in_(old_runs), Checkpoint.sequence != latest)
            counts["checkpoints"] = (
                await session.scalar(select(func.count()).select_from(Checkpoint).where(*condition))
                or 0
            )
            if not dry_run:
                await session.execute(
                    delete(Checkpoint)
                    .where(*condition)
                    .execution_options(synchronize_session=False)
                )
            if run_days is not None:
                ids = list(
                    await session.scalars(
                        select(Run.id).where(
                            Run.status.in_(terminal),
                            Run.updated_at < now - run_days * DAY_SECONDS,
                        )
                    )
                )
                counts["runs"] = len(ids)
                if ids and not dry_run:
                    await session.execute(
                        update(Run).where(Run.parent_run_id.in_(ids)).values(parent_run_id=None)
                    )
                    for table in (Event, Step, Checkpoint):
                        await session.execute(delete(table).where(table.run_id.in_(ids)))
                    await session.execute(delete(Run).where(Run.id.in_(ids)))
        return counts

    async def create_agent(self, owner: str, spec: Agent) -> dict[str, Any]:
        async with self.sessions.begin() as session:
            await session.execute(select(APIKey).where(APIKey.id == owner).with_for_update())
            existing = await session.scalar(
                select(AgentRow).where(
                    AgentRow.owner_id == owner,
                    AgentRow.name == spec.name,
                    AgentRow.version == spec.version,
                )
            )
            if existing:
                if existing.config != spec.model_dump():
                    raise StoreError("Agent versions are immutable; choose a new version")
                return public(existing)
            row = AgentRow(
                owner_id=owner, name=spec.name, version=spec.version, config=spec.model_dump()
            )
            session.add(row)
            await session.flush()
            return public(row)

    async def list_agents(self, owner: str) -> list[dict[str, Any]]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(AgentRow)
                .where(AgentRow.owner_id == owner)
                .order_by(AgentRow.created_at.desc())
                .limit(100)
            )
            return [public(row) for row in rows]

    async def get_agent(self, owner: str, agent_id: str) -> dict[str, Any]:
        async with self.sessions() as session:
            row = await session.scalar(
                select(AgentRow).where(AgentRow.id == agent_id, AgentRow.owner_id == owner)
            )
            if row is None:
                raise StoreError("Agent not found", 404)
            return public(row)

    async def create_run(
        self,
        owner: str,
        request: RunCreate,
        key: str,
        request_id: str,
        parent: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        fingerprint = hashlib.sha256(
            json.dumps({**request.model_dump(), "parent": parent}, sort_keys=True).encode()
        ).hexdigest()
        async with self.sessions.begin() as session:
            # Serializes per-owner admission and idempotency under concurrent API requests.
            await session.execute(select(APIKey).where(APIKey.id == owner).with_for_update())
            existing = await session.scalar(
                select(Run).where(Run.owner_id == owner, Run.idempotency_key == key)
            )
            if existing:
                if existing.request_hash != fingerprint:
                    raise StoreError("Idempotency key was used with a different request")
                return public(existing)
            agent = await session.scalar(
                select(AgentRow).where(AgentRow.id == request.agent_id, AgentRow.owner_id == owner)
            )
            if agent is None:
                raise StoreError("Agent not found", 404)
            active = await session.scalar(
                select(func.count())
                .select_from(Run)
                .where(Run.owner_id == owner, Run.status.not_in([s.value for s in TERMINAL]))
            )
            if (active or 0) >= self.settings.max_active_runs:
                raise StoreError("Active run limit reached", 429)
            run = Run(
                owner_id=owner,
                agent_id=agent.id,
                request_id=request_id,
                idempotency_key=key,
                request_hash=fingerprint,
                task=request.task,
                fixture=request.fixture,
                deadline=time.time() + agent.config["timeout"],
                parent_run_id=parent,
            )
            session.add(run)
            await session.flush()
            session.add(
                Checkpoint(
                    run_id=run.id,
                    sequence=0,
                    payload={
                        "files": repository(request.fixture),
                        "pending_action": None,
                        "last_result": None,
                        "tests_passed": False,
                        "history": [],
                    },
                )
            )
            event(
                session,
                run,
                "run.queued",
                agent_version=agent.version,
                provider=agent.config["provider"],
                actor=actor,
                parent_run_id=parent,
            )
            return public(run)

    async def get_run(self, owner: str, run_id: str) -> dict[str, Any]:
        async with self.sessions() as session:
            row = await session.scalar(select(Run).where(Run.id == run_id, Run.owner_id == owner))
            if row is None:
                raise StoreError("Run not found", 404)
            return public(row)

    async def list_runs(self, owner: str, before: float | None = None) -> list[dict[str, Any]]:
        async with self.sessions() as session:
            query = select(Run).where(Run.owner_id == owner)
            if before is not None:
                query = query.where(Run.created_at < before)
            rows = await session.scalars(query.order_by(Run.created_at.desc()).limit(100))
            return [public(row) for row in rows]

    async def trace(self, owner: str, run_id: str) -> dict[str, Any]:
        run = await self.get_run(owner, run_id)
        async with self.sessions() as session:
            steps = await session.scalars(
                select(Step).where(Step.run_id == run_id).order_by(Step.sequence, Step.attempt)
            )
            checkpoint = await session.scalar(
                select(Checkpoint).where(
                    Checkpoint.run_id == run_id, Checkpoint.sequence == run["checkpoint_seq"]
                )
            )
            return {
                "run": run,
                "steps": [as_dict(s) for s in steps],
                "checkpoint": as_dict(checkpoint) if checkpoint else None,
            }

    async def events(self, owner: str, run_id: str, after: int = 0) -> list[dict[str, Any]]:
        await self.get_run(owner, run_id)
        async with self.sessions() as session:
            rows = await session.scalars(
                select(Event)
                .where(Event.run_id == run_id, Event.id > after)
                .order_by(Event.id)
                .limit(200)
            )
            return [as_dict(row) for row in rows]

    async def cancel(self, owner: str, run_id: str, actor: str | None = None) -> dict[str, Any]:
        async with self.sessions.begin() as session:
            run = await session.scalar(
                select(Run).where(Run.id == run_id, Run.owner_id == owner).with_for_update()
            )
            if run is None:
                raise StoreError("Run not found", 404)
            if Status(run.status) not in TERMINAL:
                run.cancel_requested = True
                # Fence immediately: in-flight external work cannot commit after cancellation.
                set_status(session, run, Status.CANCELLED, actor=actor)
                await self._close_started(session, run, Status.CANCELLED)
            return public(run)

    async def claim(self) -> tuple[str, str] | None:
        now = time.time()
        async with self.sessions.begin() as session:
            run = await session.scalar(
                select(Run)
                .where(
                    Run.status.in_(["QUEUED", "RUNNING", "RETRYING"]),
                    Run.available_at <= now,
                    or_(Run.lease_until.is_(None), Run.lease_until < now),
                )
                .order_by(Run.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if run is None:
                return None
            if run.deadline <= now:
                set_status(session, run, Status.TIMED_OUT)
                await self._close_started(session, run, Status.TIMED_OUT)
                return None
            if run.status == "RUNNING":
                run.recoveries += 1
                pending = await session.scalars(
                    select(Step).where(Step.run_id == run.id, Step.status == "STARTED")
                )
                for step in pending:
                    step.status = "UNKNOWN"
                    step.error_type = "WorkerLost"
                if run.recoveries > 3:
                    run.error_type = "RecoveryLimit"
                    set_status(session, run, Status.FAILED)
                    return None
                event(
                    session,
                    run,
                    "worker.recovered",
                    checkpoint=run.checkpoint_seq,
                    recoveries=run.recoveries,
                )
            else:
                set_status(session, run, Status.RUNNING)
            token = uid()
            run.lease_token = token
            run.lease_until = now + self.settings.lease_seconds
            return run.id, token

    async def _fenced(self, session: AsyncSession, run_id: str, token: str) -> Run:
        run = await session.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if (
            run is None
            or run.status != "RUNNING"
            or run.lease_token != token
            or (run.lease_until or 0) <= time.time()
        ):
            raise LeaseLost()
        return run

    async def _admit_daily_spend(self, session: AsyncSession, owner: str, cost: int) -> None:
        """Owner-wide cap across all runs created in the current UTC day."""
        # Lock order is run -> api_key here; create_run takes only the api_key lock.
        await session.execute(select(APIKey).where(APIKey.id == owner).with_for_update())
        now = time.time()
        spent = await session.scalar(
            select(func.coalesce(func.sum(Run.spent_microusd), 0)).where(
                Run.owner_id == owner, Run.created_at >= now - now % DAY_SECONDS
            )
        )
        if (spent or 0) + cost > round(self.settings.daily_budget_usd * 1_000_000):
            raise StoreError("DailyBudgetExhausted")

    async def release(self, run_id: str, token: str) -> None:
        """Hand a run back on graceful shutdown without counting it as a worker loss."""
        async with self.sessions.begin() as session:
            run = await self._fenced(session, run_id, token)
            pending = await session.scalars(
                select(Step).where(Step.run_id == run.id, Step.status == "STARTED")
            )
            for step in pending:
                step.status = "UNKNOWN"
                step.error_type = "WorkerStopped"
            set_status(session, run, Status.RETRYING, reason="worker_stopped")
            run.available_at = time.time()
            run.lease_token = None
            run.lease_until = None

    async def heartbeat(self, run_id: str, token: str) -> None:
        async with self.sessions.begin() as session:
            run = await self._fenced(session, run_id, token)
            if run.deadline <= time.time():
                set_status(session, run, Status.TIMED_OUT)
                await self._close_started(session, run, Status.TIMED_OUT)
                return
            run.lease_until = time.time() + self.settings.lease_seconds

    async def context(
        self, run_id: str, token: str
    ) -> tuple[dict[str, Any], Agent, dict[str, Any]]:
        async with self.sessions.begin() as session:
            run = await self._fenced(session, run_id, token)
            agent = await session.get(AgentRow, run.agent_id)
            cp = await session.scalar(
                select(Checkpoint).where(
                    Checkpoint.run_id == run.id, Checkpoint.sequence == run.checkpoint_seq
                )
            )
            if agent is None or cp is None or cp.schema_version != 1:
                raise StoreError("Unsupported or missing checkpoint")
            return as_dict(run), Agent.model_validate(agent.config), cp.payload

    async def start_step(
        self,
        run_id: str,
        token: str,
        kind: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        reason: str | None = None,
        cost: int = 0,
        tokens: int = 0,
    ) -> dict[str, Any]:
        async with self.sessions.begin() as session:
            run = await self._fenced(session, run_id, token)
            agent = await session.get(AgentRow, run.agent_id)
            if agent is None:
                raise StoreError("Agent configuration missing")
            if run.deadline <= time.time():
                raise StoreError("DeadlineExceeded")
            if run.checkpoint_seq >= agent.config["max_steps"]:
                raise StoreError("StepLimit")
            attempts = await session.scalar(
                select(func.count())
                .select_from(Step)
                .where(Step.run_id == run.id, Step.sequence == run.checkpoint_seq)
            )
            if (attempts or 0) >= 3:
                raise StoreError("RetryLimit")
            if run.spent_microusd + cost > round(agent.config["budget_usd"] * 1_000_000):
                raise StoreError("BudgetExhausted")
            if cost:
                await self._admit_daily_spend(session, run.owner_id, cost)
            if run.charged_tokens + tokens > agent.config["max_tokens"]:
                raise StoreError("TokenLimit")
            run.spent_microusd += cost
            run.charged_tokens += tokens
            step = Step(
                run_id=run.id,
                sequence=run.checkpoint_seq,
                attempt=(attempts or 0) + 1,
                kind=kind,
                provider=provider,
                model=model,
                routing_reason=reason,
                cost_microusd=cost,
                tokens=tokens,
            )
            session.add(step)
            await session.flush()
            event(
                session,
                run,
                kind + ".started",
                step_id=step.id,
                attempt=step.attempt,
                provider=provider,
                model=model,
                routing_reason=reason,
            )
            return as_dict(step)

    async def finish_step(
        self,
        run_id: str,
        token: str,
        step_id: str,
        payload: dict[str, Any],
        detail: dict[str, Any],
        duration_ms: int,
        actual_cost: int | None = None,
        actual_tokens: int | None = None,
    ) -> None:
        async with self.sessions.begin() as session:
            run = await self._fenced(session, run_id, token)
            step = await session.get(Step, step_id)
            if step is None or step.run_id != run.id or step.status != "STARTED":
                raise LeaseLost()
            if actual_cost is not None and actual_tokens is not None:
                # Record actual usage; an over-limit result terminates below before further work.
                run.spent_microusd += actual_cost - step.cost_microusd
                run.charged_tokens += actual_tokens - step.tokens
                step.cost_microusd = actual_cost
                step.tokens = actual_tokens
            step.status = "SUCCEEDED"
            step.detail = detail
            step.duration_ms = duration_ms
            run.checkpoint_seq += 1
            session.add(Checkpoint(run_id=run.id, sequence=run.checkpoint_seq, payload=payload))
            event(
                session,
                run,
                step.kind + ".completed",
                step_id=step.id,
                duration_ms=duration_ms,
                checkpoint=run.checkpoint_seq,
            )
            agent = await session.get(AgentRow, run.agent_id)
            if agent is None:
                raise StoreError("Agent configuration missing")
            if (
                run.spent_microusd > round(agent.config["budget_usd"] * 1_000_000)
                or run.charged_tokens > agent.config["max_tokens"]
            ):
                run.error_type = "ProviderUsageExceededReservation"
                set_status(session, run, Status.FAILED, error_type=run.error_type)

    async def fail_step(
        self, run_id: str, token: str, step_id: str, error_type: str, delay: float, retryable: bool
    ) -> None:
        async with self.sessions.begin() as session:
            run = await self._fenced(session, run_id, token)
            step = await session.get(Step, step_id)
            if step is None or step.run_id != run.id or step.status != "STARTED":
                raise LeaseLost()
            step.status = "FAILED"
            step.error_type = error_type
            step.duration_ms = max(0, int((time.time() - step.started_at) * 1000))
            run.error_type = error_type
            event(session, run, step.kind + ".failed", error_type=error_type, step_id=step.id)
            if retryable and step.attempt < 3:
                set_status(session, run, Status.RETRYING, delay_seconds=delay)
                run.available_at = time.time() + delay
                run.lease_until = None
                run.lease_token = None
            else:
                set_status(session, run, Status.FAILED, error_type=error_type)

    async def finish_run(
        self,
        run_id: str,
        token: str,
        status: Status,
        output: str | None = None,
        error: str | None = None,
    ) -> None:
        async with self.sessions.begin() as session:
            run = await self._fenced(session, run_id, token)
            if run.deadline <= time.time():
                status, output, error = Status.TIMED_OUT, None, "DeadlineExceeded"
            run.output, run.error_type = output, error
            set_status(session, run, status, error_type=error)
            await self._close_started(session, run, status)

    async def prior_failures(self, run_id: str, sequence: int) -> list[str]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(Step.provider).where(
                    Step.run_id == run_id,
                    Step.sequence == sequence,
                    Step.status.in_(["FAILED", "UNKNOWN"]),
                )
            )
            return [row for row in rows if row is not None]
