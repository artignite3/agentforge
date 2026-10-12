"""Capture real bounded tool results without submitting or changing application jobs."""

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path.insert(0, str(ROOT.parents[1] / "src"))
    from agentforge.domain import Action, ToolRequest
    from agentforge.fixtures import repository
    from agentforge.sandbox import DockerExecutor

    files = repository("clamp")
    executor = DockerExecutor("agentforge-tool:local")

    def invoke(action):
        return executor.execute(
            ToolRequest(operation_id=str(uuid.uuid4()), action=action, files=files)
        ).model_dump()

    before = invoke(Action(operation="run_tests", explanation="Reproduce the bundled regression."))
    fixed = files["stats.py"].replace("min(low, max(high, value))", "max(low, min(high, value))")
    write = invoke(
        Action(
            operation="write_file",
            path="stats.py",
            content=fixed,
            explanation="Correct the clamp boundary calculation.",
        )
    )
    files["stats.py"] = fixed
    after = invoke(Action(operation="run_tests", explanation="Verify unchanged original tests."))
    assert before["exit_code"] == 1 and write["exit_code"] == 0 and after["exit_code"] == 0
    result = {
        "fixture": "clamp",
        "capture": "Real disposable Docker containers via DockerExecutor",
        "before": before,
        "write": write,
        "after": after,
        "original_source": repository("clamp")["stats.py"],
        "repaired_source": fixed,
        "original_tests": files["test_stats.py"],
    }
    (ROOT / "public/reference/fixture-evidence.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        "Real Docker fixture evidence captured: original tests exit 1, source write exit 0, unchanged tests exit 0."
    )


if __name__ == "__main__":
    main()
