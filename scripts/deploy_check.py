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
    edge = services["edge"]
    if {(str(p["published"]), p["target"]) for p in edge["ports"]} != {("80", 8081), ("443", 8443)}:
        raise ValueError("Edge must publish only HTTP and HTTPS")
    for name in ("api", "worker", "migrate"):
        env = services[name]["environment"]
        if env["AGENTFORGE_ENVIRONMENT"] != "production" or env["AGENTFORGE_CORS_ORIGINS"] != "[]":
            raise ValueError("Require production mode and same-origin browser access")
        keys = [env["AGENTFORGE_API_KEY"], env["AGENTFORGE_SANDBOX_KEY"]]
        if any(len(key) < 32 for key in keys) or keys[0] == keys[1]:
            raise ValueError("API and gateway need distinct keys of at least 32 characters")
        if not env["AGENTFORGE_DATABASE_URL"].startswith("postgresql+asyncpg://"):
            raise ValueError("Production requires PostgreSQL")
        if not env["AGENTFORGE_REDIS_URL"].startswith("redis://"):
            raise ValueError("Production requires Redis")
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
        print("PASS: resolved production config, private ports, gateway socket, keys, and origins")
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
