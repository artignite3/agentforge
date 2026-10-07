import pytest

from agentforge.config import Settings
from agentforge.security import owner_id
from agentforge.store import Store


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        api_key="test-api-key-" + "x" * 32,
        sandbox_key="test-tool-key-" + "y" * 32,
    )


@pytest.fixture
async def store(settings):
    database = Store(settings)
    await database.create_schema()
    await database.register_key(owner_id(settings.api_key.get_secret_value()))
    yield database
    await database.engine.dispose()


@pytest.fixture
def owner(settings):
    return owner_id(settings.api_key.get_secret_value())
