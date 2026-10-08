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
