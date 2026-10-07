"""Submit a genuine API job and print a compact, inspectable execution trace."""

import argparse
import os

from agentforge import Agent, AgentForge
from agentforge.config import get_settings

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
parser.add_argument("--provider", choices=["demo", "auto", "openai", "gemini"], default="demo")
parser.add_argument("--fixture", choices=["mean", "clamp"], default="mean")
args = parser.parse_args()

settings = get_settings()
key = os.getenv("AGENTFORGE_API_KEY") or settings.api_key.get_secret_value()
with AgentForge(api_key=key, base_url=args.url) as client:
    agent = Agent(name="repo-engineer-" + args.provider, provider=args.provider)
    run = client.run(
        agent=agent,
        task="Inspect the repository, reproduce the failure, repair stats.py and rerun the original tests.",
        fixture=args.fixture,
    )
    print("Submitted", run["id"])
    result = client.wait(run["id"])
    trace = client.trace(run["id"])
    for step in trace["steps"]:
        print(
            f"{step['sequence']:02d} {step['kind']:6} {step['status']:9} {step['duration_ms']} ms  {step['routing_reason'] or step['detail'].get('operation', '')}"
        )
    print(result["status"], result["output"] or result["error_type"])
    if result["status"] != "COMPLETED":
        raise SystemExit(1)
