"""Validate resolved production Compose without displaying environment secrets."""

import argparse
import json
import subprocess
from pathlib import Path


def compose_command(env_file: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.production.yml",
    ]


PROVIDER_SECRETS = ("AGENTFORGE_OPENAI_KEY", "AGENTFORGE_GEMINI_KEY")
# Who may join each network. Internal networks have no route off the host.
NETWORK_MEMBERS = {
    "edge": {"edge", "frontend"},
    "web": {"frontend", "api"},
    "data": {"api", "worker", "migrate", "postgres"},
    "cache": {"api", "redis"},
    "tools": {"worker", "sandbox"},
    "egress": {"worker"},
}
INTERNAL_NETWORKS = {"data", "cache", "tools"}


def _secret(env: dict, name: str) -> str:
    value = env.get(name) or ""
    if len(value) < 32:
        raise ValueError(f"{name} must be set to at least 32 characters")
    return value


def validate(config: dict) -> None:
    """Inspect merged ports/trust boundaries rather than the override in isolation."""
    services = config["services"]
    for name, service in services.items():
        ports = service.get("ports", [])
        if name != "edge" and ports:
            raise ValueError("Only the TLS edge may publish host ports")
        if name != "sandbox":
            for mount in service.get("volumes", []):
                if "docker.sock" in mount.get("source", "") or "docker.sock" in mount["target"]:
                    raise ValueError("Docker socket may be mounted only into the gateway")
        if service.get("network_mode") != "none":
            options = (service.get("logging") or {}).get("options") or {}
            if not options.get("max-size"):
                raise ValueError(f"{name} needs bounded log rotation")
        for network in service.get("networks") or {}:
            if name not in NETWORK_MEMBERS.get(network, set()):
                raise ValueError(f"{name} may not join network {network}")
    for network in INTERNAL_NETWORKS:
        if not config.get("networks", {}).get(network, {}).get("internal"):
            raise ValueError(f"Network {network} must be internal")
    edge = services["edge"]
    if {(str(p["published"]), p["target"]) for p in edge["ports"]} != {("80", 8081), ("443", 8443)}:
        raise ValueError("Edge must publish only HTTP and HTTPS")
    envs = {name: services[name]["environment"] for name in ("api", "worker", "migrate")}
    for env in envs.values():
        if env["AGENTFORGE_ENVIRONMENT"] != "production" or env["AGENTFORGE_CORS_ORIGINS"] != "[]":
            raise ValueError("Require production mode and same-origin browser access")
        if not env["AGENTFORGE_DATABASE_URL"].startswith("postgresql+asyncpg://"):
            raise ValueError("Production requires PostgreSQL")
    api, worker, migrate = envs["api"], envs["worker"], envs["migrate"]
    operator_key = _secret(api, "AGENTFORGE_API_KEY")
    sandbox_key = _secret(worker, "AGENTFORGE_SANDBOX_KEY")
    if operator_key == sandbox_key:
        raise ValueError("API and gateway need distinct keys")
    if _secret(services["sandbox"]["environment"], "AGENTFORGE_SANDBOX_KEY") != sandbox_key:
        raise ValueError("Worker and gateway must share the gateway key")
    if not api.get("AGENTFORGE_REDIS_URL", "").startswith("redis://"):
        raise ValueError("Production requires Redis")
    if api.get("AGENTFORGE_TRUSTED_PROXY_HOPS") != "2":
        raise ValueError("The API sits behind Caddy and nginx: trust exactly two proxy hops")
    # Least privilege: each process holds only the credentials it uses.
    for secret in ("AGENTFORGE_SANDBOX_KEY", *PROVIDER_SECRETS):
        if api.get(secret):
            raise ValueError(f"The public API must not receive {secret}")
    if worker.get("AGENTFORGE_API_KEY"):
        raise ValueError("The worker must not receive the operator API key")
    if any(
        migrate.get(s) for s in ("AGENTFORGE_API_KEY", "AGENTFORGE_SANDBOX_KEY", *PROVIDER_SECRETS)
    ):
        raise ValueError("Migrations must not receive application secrets")
    from scripts.prepare_deploy import public_hostname

    public_hostname(edge["environment"]["AGENTFORGE_DOMAIN"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--require-engine", action="store_true")
    args = parser.parse_args()
    try:
        if not args.env_file.is_file():
            raise ValueError("Production environment file is missing")
        result = subprocess.run(
            [*compose_command(args.env_file), "config", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise ValueError("Compose configuration failed; check Compose version/environment")
        validate(json.loads(result.stdout))
        print(
            "PASS: resolved production config: ports, networks, socket, per-service secrets, logs"
        )
        if args.require_engine:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.OSType}}"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode or result.stdout.strip() != "linux":
                raise ValueError("A running Linux Docker engine is required")
            print("PASS: Linux Docker engine reachable")
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        # Do not dump Compose output: it contains resolved credentials.
        message = (
            str(exc) if isinstance(exc, ValueError) else "Deployment validation could not finish"
        )
        parser.exit(1, f"FAIL: {message}\n")


if __name__ == "__main__":
    # Support direct invocation from the repository root without an editable install.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
