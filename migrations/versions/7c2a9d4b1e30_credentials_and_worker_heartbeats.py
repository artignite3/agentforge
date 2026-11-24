"""credentials and worker heartbeats

Revision ID: 7c2a9d4b1e30
Revises: 1ef9fd4d71fb

Existing owners were identified by SHA-256(operator key). Each becomes an owner with one
admin bootstrap credential holding that same hash, so the deployed key keeps working and
no agents or runs change ownership.
"""

import time
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c2a9d4b1e30"
down_revision: str | Sequence[str] | None = "1ef9fd4d71fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    credentials = op.create_table(
        "credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("bootstrap", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=True),
        sa.Column("revoked_at", sa.Float(), nullable=True),
        sa.Column("revoked_by", sa.String(length=36), nullable=True),
        sa.Column("last_used_at", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["api_keys.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_credentials_owner_id"), "credentials", ["owner_id"], unique=False)
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.Float(), nullable=False),
        sa.Column("seen_at", sa.Float(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("sandbox_ready", sa.Boolean(), nullable=False),
        sa.Column("providers", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_worker_heartbeats_seen_at"), "worker_heartbeats", ["seen_at"], unique=False
    )
    owners = op.get_bind().execute(sa.text("SELECT id FROM api_keys")).scalars().all()
    if owners:
        op.bulk_insert(
            credentials,
            [
                {
                    "id": str(uuid.uuid4()),
                    "owner_id": owner,
                    "key_hash": owner,
                    "label": "bootstrap",
                    "role": "admin",
                    "bootstrap": True,
                    "created_at": time.time(),
                }
                for owner in owners
            ],
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_worker_heartbeats_seen_at"), table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
    op.drop_index(op.f("ix_credentials_owner_id"), table_name="credentials")
    op.drop_table("credentials")
