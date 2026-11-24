"""Operator CLI with direct database access: key management and data retention.

Run inside the API or worker container (it needs AGENTFORGE_DATABASE_URL), for example:
    docker compose exec api python -m agentforge.admin keys create --label ci --role read
Plaintext keys are printed once, on creation only.
"""

import argparse
import asyncio
import json
import time

from sqlalchemy import select

from agentforge.config import get_settings
from agentforge.models import APIKey
from agentforge.store import Store, StoreError


async def only_owner(store: Store) -> str:
    async with store.sessions() as session:
        owners = list(await session.scalars(select(APIKey.id).limit(2)))
    if len(owners) != 1:
        raise StoreError("Expected exactly one owner; start the API once to bootstrap it")
    return owners[0]


async def run(args: argparse.Namespace) -> None:
    store = Store(get_settings())
    try:
        if args.command == "prune":
            counts = await store.prune(args.checkpoint_days, args.run_days, args.dry_run)
            verb = "Would delete" if args.dry_run else "Deleted"
            print(f"{verb} {counts['checkpoints']} checkpoints and {counts['runs']} runs.")
            return
        owner = await only_owner(store)
        if args.action == "create":
            expires = time.time() + args.expires_days * 86400 if args.expires_days else None
            record, key = await store.create_credential(
                owner, args.label, args.role, expires, created_by="cli"
            )
            print(f"Created {record['role']} key {record['id']} ({record['label']}).")
            print("Key (shown once; store it in a secret manager):")
            print(key)
        elif args.action == "list":
            for row in await store.list_credentials(owner):
                print(
                    json.dumps(
                        {
                            k: row[k]
                            for k in (
                                "id",
                                "label",
                                "role",
                                "bootstrap",
                                "created_at",
                                "expires_at",
                                "revoked_at",
                                "last_used_at",
                            )
                        }
                    )
                )
        else:
            record = await store.revoke_credential(owner, args.key_id, revoked_by="cli")
            print(f"Revoked {record['id']} ({record['label']}).")
    finally:
        await store.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    keys = commands.add_parser("keys", help="Create, list, or revoke API keys")
    actions = keys.add_subparsers(dest="action", required=True)
    create = actions.add_parser("create")
    create.add_argument("--label", required=True)
    create.add_argument("--role", choices=["read", "submit", "admin"], required=True)
    create.add_argument("--expires-days", type=float)
    actions.add_parser("list")
    revoke = actions.add_parser("revoke")
    revoke.add_argument("key_id")
    prune = commands.add_parser("prune", help="Delete old data of terminal runs")
    prune.add_argument(
        "--checkpoint-days",
        type=float,
        required=True,
        help="Drop intermediate checkpoints of terminal runs older than this",
    )
    prune.add_argument(
        "--run-days", type=float, help="Also delete whole terminal runs older than this"
    )
    prune.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except StoreError as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
