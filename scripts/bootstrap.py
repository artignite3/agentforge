"""Generate untracked local credentials without printing them."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print(".env already exists; credentials preserved.")
else:
    content = (root / ".env.example").read_text(encoding="utf-8")
    for name in ("AGENTFORGE_API_KEY", "AGENTFORGE_SANDBOX_KEY", "POSTGRES_PASSWORD"):
        content = content.replace(name + "=\n", name + "=" + secrets.token_urlsafe(36) + "\n", 1)
    target.write_text(content, encoding="utf-8")
    target.chmod(0o600)
    print("Generated .env. Copy AGENTFORGE_API_KEY into the dashboard connection dialog.")
