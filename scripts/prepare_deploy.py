"""Create a fresh deployment environment without overwriting local credentials."""

import argparse
import ipaddress
import os
import re
import secrets
from pathlib import Path


def public_hostname(value: str) -> str:
    """Accept a hostname, never a URL, IP, Caddy expression, or reserved example."""
    value = value.lower()
    labels = value.split(".")
    if (
        len(value) > 253
        or len(labels) < 2
        or not re.fullmatch(r"[a-z]{2,63}|xn--[a-z0-9-]+", labels[-1])
        or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels)
        or labels[-1] in {"test", "invalid", "example", "localhost", "local"}
        or value in {"example.com", "example.net", "example.org"}
        or value.endswith((".example.com", ".example.net", ".example.org"))
    ):
        raise ValueError("Supply your public DNS hostname without a scheme, path, or port")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError("Supply a public DNS hostname, not an IP address")


def prepare(domain: str, gid: int, root: Path) -> Path:
    domain = public_hostname(domain)
    if not 0 <= gid <= 2**31 - 1:
        raise ValueError("Docker socket group ID is out of range")
    values = {
        "AGENTFORGE_API_KEY": secrets.token_urlsafe(36),
        "AGENTFORGE_SANDBOX_KEY": secrets.token_urlsafe(36),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(36),
        "AGENTFORGE_ENVIRONMENT": "production",
        "AGENTFORGE_CORS_ORIGINS": "[]",
        "DOCKER_GID": str(gid),
    }
    lines = ["# Generated for this deployment; keep private.", f"AGENTFORGE_DOMAIN={domain}"]
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        name = line.split("=", 1)[0]
        lines.append(f"{name}={values[name]}" if name in values else line)
    target = root / ".env.production"
    # Exclusive creation and restrictive permissions from the first write on Linux.
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--docker-gid", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        gid = args.docker_gid
        if gid is None:
            gid = Path("/var/run/docker.sock").stat().st_gid
        prepare(args.domain, gid, root)
    except FileExistsError:
        parser.exit(1, ".env.production already exists; credentials preserved.\n")
    except (OSError, ValueError):
        parser.exit(1, "Preparation failed. Check domain/socket; supply --docker-gid if needed.\n")
    print("Created .env.production with fresh credentials. No secrets were printed.")
    print("Set optional provider keys privately before starting the production stack.")


if __name__ == "__main__":
    main()
