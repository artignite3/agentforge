"""Kill this Compose project's worker after checkpoint four and verify real recovery."""

import argparse
import subprocess
import time

from agentforge import Agent, AgentForge
from agentforge.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    with AgentForge(get_settings().api_key.get_secret_value(), args.url) as client:
        agent = Agent(name="chaos-repo-engineer", provider="demo", timeout=120)
        run = client.run(
            agent, "Repair the mean fixture while the worker is killed after checkpoint four."
        )
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            current = client.get(run["id"])
            if current["checkpoint_seq"] >= 4:
                break
            time.sleep(0.3)
        else:
            raise RuntimeError("Run did not reach the target checkpoint")
        if current["status"] == "COMPLETED":
            raise RuntimeError("Run completed before injection; rerun the demo")
        print(
            "Killing this project's worker at checkpoint",
            current["checkpoint_seq"],
            "run",
            run["id"],
        )
        subprocess.run(["docker", "compose", "kill", "-s", "SIGKILL", "worker"], check=True)
        subprocess.run(["docker", "compose", "up", "-d", "--no-deps", "worker"], check=True)
        final = client.wait(run["id"], timeout=90, poll_interval=2)
        trace = client.trace(run["id"])
        if final["status"] != "COMPLETED" or final["recoveries"] < 1:
            raise RuntimeError("Recovery did not complete successfully")
        successful = [s for s in trace["steps"] if s["status"] == "SUCCEEDED"]
        if len(successful) != 9:
            raise RuntimeError("Unexpected repeated committed steps")
        print(
            "Recovered and completed:",
            final["id"],
            "recoveries:",
            final["recoveries"],
            "successful steps:",
            len(successful),
        )


if __name__ == "__main__":
    main()
