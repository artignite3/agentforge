"""Small reproducible A/B evaluation. Reports measured outcomes, never assumed quality."""

import argparse
import json
from pathlib import Path
from statistics import mean

from agentforge import Agent, AgentForge
from agentforge.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--provider", choices=["demo", "auto", "openai", "gemini"], default="demo")
    parser.add_argument("--output", default="evals/results/comparison.json")
    args = parser.parse_args()
    dataset = json.loads(Path(__file__).with_name("dataset.json").read_text())
    results = []
    prompts = {
        "v1": "Repair the bug without modifying tests. Verify the fix.",
        "v2": "First reproduce the test failure, inspect the source, make the smallest repair, then verify all original tests. Avoid unnecessary calls.",
    }
    with AgentForge(get_settings().api_key.get_secret_value(), args.url) as client:
        for version, instructions in prompts.items():
            agent = Agent(
                name="eval-repo-" + args.provider,
                version=version,
                provider=args.provider,
                instructions=instructions,
            )
            for case in dataset:
                run = client.run(agent, case["task"], case["fixture"])
                final = client.wait(run["id"])
                trace = client.trace(run["id"])
                steps = trace["steps"]
                tools = [s for s in steps if s["kind"] == "tool"]
                results.append(
                    {
                        "case": case["id"],
                        "version": version,
                        "provider_policy": args.provider,
                        "run_id": run["id"],
                        "completed": final["status"] == "COMPLETED",
                        "regression_passed": bool(trace["checkpoint"]["payload"]["tests_passed"]),
                        "tool_success_rate": mean(s["detail"].get("exit_code") == 0 for s in tools)
                        if tools
                        else 0,
                        "retries": sum(s["attempt"] > 1 for s in steps),
                        "tool_calls": len(tools),
                        "latency_ms": round((final["updated_at"] - final["created_at"]) * 1000),
                        "charged_tokens": final["charged_tokens"],
                        "estimated_cost_usd": final["spent_microusd"] / 1e6,
                    }
                )
    report = {
        "note": "Demo uses the same scripted planner for both prompt versions; it evaluates infrastructure, not model intelligence. Task success here means supplied regression tests passed, not a semantic proof.",
        "results": results,
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    for version in prompts:
        group = [r for r in results if r["version"] == version]
        print(
            f"{version}: {sum(r['completed'] and r['regression_passed'] for r in group)}/{len(group)} verified; mean {mean(r['latency_ms'] for r in group):.0f} ms; ${sum(r['estimated_cost_usd'] for r in group):.4f}"
        )
    print("Wrote", target)
    if not all(r["completed"] and r["regression_passed"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
