"""Deployment checks exercise actual Compose merging and hostile hostname inputs."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.deploy_check import compose_command, validate
from scripts.prepare_deploy import prepare, public_hostname


@pytest.mark.parametrize(
    "domain",
    [
        "https://forge.dev",
        "forge.dev:443",
        "forge.dev\nrespond bad",
        "*.forge.dev",
        "127.0.0.1",
        "example.com",
        "forge.local",
        "forge.dev/path",
        "-forge.dev",
    ],
)
def test_deployment_domain_rejects_urls_reserved_names_and_config_injection(domain):
    with pytest.raises(ValueError):
        public_hostname(domain)


def test_prepare_preserves_existing_credentials_and_local_environment(tmp_path):
    (tmp_path / ".env.example").write_text(
        Path(".env.example").read_text(encoding="utf-8"), encoding="utf-8"
    )
    local = tmp_path / ".env"
    local.write_text("existing local environment", encoding="utf-8")
    production = prepare("forge.project.dev", 998, tmp_path)
    first = production.read_bytes()
    with pytest.raises(FileExistsError):
        prepare("other.project.dev", 998, tmp_path)
    assert production.read_bytes() == first
    assert local.read_text() == "existing local environment"
    if os.name != "nt":
        assert production.stat().st_mode & 0o777 == 0o600


def test_real_compose_merge_removes_application_ports(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI is required")
    (tmp_path / ".env.example").write_text(
        Path(".env.example").read_text(encoding="utf-8"), encoding="utf-8"
    )
    env_file = prepare("forge.project.dev", 998, tmp_path)
    # The caller's provider keys and local settings must not affect this test.
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("AGENTFORGE_") and key not in {"DOCKER_GID", "POSTGRES_PASSWORD"}
    }
    result = subprocess.run(
        [*compose_command(env_file), "config", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=30,
        env=clean_env,
    )
    assert result.returncode == 0, "Compose merge failed (resolved secrets omitted)"
    config = json.loads(result.stdout)
    validate(config)
    config["services"]["api"]["ports"] = [{"published": "8000", "target": 8000}]
    with pytest.raises(ValueError, match="Only the TLS edge"):
        validate(config)


def valid_config():
    """A minimal resolved production config, as `docker compose config` would emit it."""
    logging = {"driver": "json-file", "options": {"max-size": "10m"}}
    prod = {"AGENTFORGE_ENVIRONMENT": "production", "AGENTFORGE_CORS_ORIGINS": "[]"}
    db = {**prod, "AGENTFORGE_DATABASE_URL": "postgresql+asyncpg://u:p@postgres/agentforge"}

    def service(networks, **extra):
        return {"networks": dict.fromkeys(networks), "logging": logging, **extra}

    return {
        "networks": {
            n: {"internal": n in {"data", "cache", "tools"}}
            for n in ("edge", "web", "data", "cache", "tools", "egress")
        },
        "services": {
            "edge": service(
                ["edge"],
                ports=[{"published": "80", "target": 8081}, {"published": "443", "target": 8443}],
                environment={"AGENTFORGE_DOMAIN": "forge.project.dev"},
            ),
            "frontend": service(["web", "edge"]),
            "api": service(
                ["web", "data", "cache"],
                environment={
                    **db,
                    "AGENTFORGE_API_KEY": "a" * 40,
                    "AGENTFORGE_REDIS_URL": "redis://redis:6379/0",
                    "AGENTFORGE_TRUSTED_PROXY_HOPS": "2",
                },
            ),
            "worker": service(
                ["data", "tools", "egress"],
                environment={
                    **db,
                    "AGENTFORGE_SANDBOX_KEY": "s" * 40,
                    "AGENTFORGE_GEMINI_KEY": "g" * 40,
                },
            ),
            "migrate": service(["data"], environment=db),
            "sandbox": service(
                ["tools"],
                environment={"AGENTFORGE_SANDBOX_KEY": "s" * 40},
                volumes=[{"source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}],
            ),
            "postgres": service(["data"]),
            "redis": service(["cache"]),
            "tool-image": {"network_mode": "none"},
        },
    }


def test_valid_segmented_least_privilege_config_passes():
    validate(valid_config())


@pytest.mark.parametrize(
    "mutate, message",
    [
        (
            lambda c: c["services"]["api"]["environment"].update(AGENTFORGE_GEMINI_KEY="g" * 40),
            "must not receive AGENTFORGE_GEMINI_KEY",
        ),
        (
            lambda c: c["services"]["api"]["environment"].update(AGENTFORGE_SANDBOX_KEY="s" * 40),
            "must not receive AGENTFORGE_SANDBOX_KEY",
        ),
        (
            lambda c: c["services"]["worker"]["environment"].update(AGENTFORGE_API_KEY="a" * 40),
            "worker must not receive",
        ),
        (
            lambda c: c["services"]["edge"]["networks"].update(data=None),
            "edge may not join network data",
        ),
        (
            lambda c: c["services"]["frontend"]["networks"].update(cache=None),
            "frontend may not join network cache",
        ),
        (lambda c: c["networks"]["data"].update(internal=False), "data must be internal"),
        (lambda c: c["services"]["redis"].pop("logging"), "redis needs bounded log rotation"),
        (
            lambda c: c["services"]["api"]["environment"].update(AGENTFORGE_TRUSTED_PROXY_HOPS="5"),
            "two proxy hops",
        ),
        (
            lambda c: c["services"]["sandbox"]["environment"].update(
                AGENTFORGE_SANDBOX_KEY="x" * 40
            ),
            "share the gateway key",
        ),
        (
            lambda c: c["services"]["worker"]["environment"].update(
                AGENTFORGE_SANDBOX_KEY="a" * 40
            ),
            "distinct keys",
        ),
    ],
)
def test_topology_and_secret_violations_are_rejected(mutate, message):
    config = valid_config()
    mutate(config)
    with pytest.raises(ValueError, match=message):
        validate(config)
