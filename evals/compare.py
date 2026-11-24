"""Small reproducible A/B evaluation. Reports measured outcomes, never assumed quality.

Each (prompt version, case) pair runs ``--trials`` times. Latency is split into queue wait
(submission until first claim) and execution (first claim until terminal state), because
end-to-end time on a shared single-worker queue mostly measures other jobs. Summaries use
the median and nearest-rank p95; with few trials these are descriptive, not significant.
"""

import argparse
import json
import math
import time
from pathlib import Path
from statistics import median
from typing import Any

import httpx

from agentforge import Agent, AgentForge
from agentforge.models import uid
from agentforge.sdk import api_key_from_environment

PROMPTS = {
    "v1": "Repair the bug without modifying tests. Verify the fix.",
    "v2": "First reproduce the test failure, inspect the source, make the smallest repair, then verify all original tests. Avoid unnecessary calls.",
}


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def measure(client: AgentForge, run_id: str, timeout: float) -> dict[str, Any]:
    final = client.wait(run_id, timeout=timeout)
    trace = client.trace(run_id)
    events = client.http.get(f"/v1/runs/{run_id}/events").json()
    steps = trace["steps"]
    tools = [s for s in steps if s["kind"] == "tool"]
    claimed = next((e["at"] for e in events if e["kind"] == "run.running"), final["created_at"])
    return {
        "status": final["status"],
        "error_type": final["error_type"],
        "verified": final["status"] == "COMPLETED",
        "regression_passed": bool(
            (trace["checkpoint"] or {}).get("payload", {}).get("tests_passed")
        ),
        "model_calls": sum(s["kind"] == "model" for s in steps),
        "tool_calls": len(tools),
        "policy_rejections": sum(
            s["detail"].get("timeout_reason") == "PolicyViolation" for s in tools
        ),
        "retried_attempts": sum(s["attempt"] > 1 for s in steps),
        "recoveries": final["recoveries"],
        "queue_wait_ms": round((claimed - final["created_at"]) * 1000),
        "execution_ms": round((final["updated_at"] - claimed) * 1000),
        "charged_tokens": final["charged_tokens"],
        "estimated_cost_usd": final["spent_microusd"] / 1e6,
    }


def summarize(group: list[dict[str, Any]]) -> dict[str, Any]:
    finished = [r for r in group if "execution_ms" in r]
    latencies = [r["execution_ms"] for r in finished]
    return {
        "runs": len(group),
        "verified": sum(r.get("verified", False) for r in group),
        "verified_rate": round(sum(r.get("verified", False) for r in group) / len(group), 3),
        "client_errors": len(group) - len(finished),
        "execution_ms_median": median(latencies) if latencies else None,
        "execution_ms_p95": p95(latencies) if latencies else None,
        "mean_model_calls": round(sum(r["model_calls"] for r in finished) / len(finished), 2)
        if finished
        else None,
        "total_estimated_cost_usd": round(sum(r["estimated_cost_usd"] for r in finished), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--provider", choices=["demo", "auto", "openai", "gemini"], default="demo")
    parser.add_argument("--trials", type=int, default=3, help="Repetitions per version and case")
    parser.add_argument("--timeout", type=float, default=180, help="Client wait per run (s)")
    parser.add_argument("--output", default="evals/results/comparison.json")
    args = parser.parse_args()
    if not 1 <= args.trials <= 50:
        parser.error("--trials must be between 1 and 50")
    dataset = json.loads(Path(__file__).with_name("dataset.json").read_text())
    session = uid()[:8]  # Unique idempotency keys per invocation; stable within it.
    results: list[dict[str, Any]] = []
    with AgentForge(api_key_from_environment(), args.url) as client:
        for version, instructions in PROMPTS.items():
            agent = Agent(
                name="eval-repo-" + args.provider,
                version=version,
                provider=args.provider,
                instructions=instructions,
            )
            for case in dataset:
                for trial in range(1, args.trials + 1):
                    record: dict[str, Any] = {
                        "case": case["id"],
                        "version": version,
                        "trial": trial,
                    }
                    try:
                        run = client.run(
                            agent,
                            case["task"],
                            case["fixture"],
                            idempotency_key=f"eval-{session}-{version}-{case['id']}-{trial}",
                        )
                        record["run_id"] = run["id"]
                        record.update(measure(client, run["id"], args.timeout))
                    except (httpx.HTTPError, TimeoutError) as exc:
                        # Record the failure instead of discarding every earlier measurement.
                        record["client_error"] = type(exc).__name__
                    results.append(record)
    summary = {v: summarize([r for r in results if r["version"] == v]) for v in PROMPTS}
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider_policy": args.provider,
        "trials_per_case": args.trials,
        "cases": [case["id"] for case in dataset],
        "note": (
            "Demo uses the same scripted planner for both prompt versions, so identical results "
            "are expected: this measures infrastructure, not model intelligence. Verified means "
            "the unchanged tests reported the expected test count and OK. Costs are estimates "
            "from operator-configured rates, not invoices."
        ),
        "summary": summary,
        "results": results,
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    for version, stats in summary.items():
        print(
            f"{version}: {stats['verified']}/{stats['runs']} verified; "
            f"execution median {stats['execution_ms_median']} ms, p95 {stats['execution_ms_p95']} ms; "
            f"est. ${stats['total_estimated_cost_usd']:.4f}"
        )
    print("Wrote", target)
    if any(stats["verified"] < stats["runs"] for stats in summary.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
