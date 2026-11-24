"""Real PostgreSQL locking behavior; SQLite cannot validate SKIP LOCKED."""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from agentforge.domain import Agent, RunCreate
from agentforge.security import owner_id
from agentforge.store import Store

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not os.getenv("POSTGRES_TEST_URL"), reason="Set POSTGRES_TEST_URL"),
]


async def test_concurrent_claims_and_idempotent_admission(settings):
    settings.database_url = os.environ["POSTGRES_TEST_URL"]
    database = Store(settings)
    schema = "test_" + uuid.uuid4().hex
    async with database.engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    database.engine = database.engine.execution_options(schema_translate_map={None: schema})
    database.sessions = async_sessionmaker(database.engine, expire_on_commit=False)
    try:
        await database.create_schema()
        owner = owner_id(settings.api_key.get_secret_value())
        await database.bootstrap_credential(settings.api_key.get_secret_value())
        agent = await database.create_agent(owner, Agent())
        spec = RunCreate(agent_id=agent["id"])
        duplicates = await asyncio.gather(
            *[database.create_run(owner, spec, "same", "req") for _ in range(6)]
        )
        assert len({run["id"] for run in duplicates}) == 1
        for index in range(4):
            await database.create_run(owner, spec, f"unique-{index}", "req")
        claims = await asyncio.gather(*[database.claim() for _ in range(10)])
        claimed = [value[0] for value in claims if value]
        assert len(claimed) == 5
        assert len(set(claimed)) == 5
    finally:
        async with database.engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await database.engine.dispose()
