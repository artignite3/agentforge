"""Write a binary-safe PostgreSQL backup, then verify its archive directory."""

import argparse
import os
import subprocess
from pathlib import Path

from deploy_check import compose_command


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    created = False
    try:
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        command = [*compose_command(args.env_file), "exec", "-T", "postgres"]
        with os.fdopen(descriptor, "wb") as stream:
            result = subprocess.run(
                [*command, "pg_dump", "-U", "agentforge", "-d", "agentforge", "-Fc"],
                stdout=stream,
                stderr=subprocess.PIPE,
                timeout=300,
            )
        if result.returncode:
            raise ValueError("Database dump failed")
        with args.output.open("rb") as stream:
            result = subprocess.run(
                [*command, "pg_restore", "--list"],
                stdin=stream,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        if result.returncode:
            raise ValueError("Backup archive validation failed")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        if created:
            args.output.unlink(missing_ok=True)
        parser.exit(1, "Backup failed; existing files were preserved. Check host privately.\n")
    print("Backup created and archive directory verified. Encrypt and copy it off-host.")
    print("Archive validation does not replace a full restoration drill.")


if __name__ == "__main__":
    main()
