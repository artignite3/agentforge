import pytest
from pydantic import ValidationError

from agentforge.domain import (
    Action,
    Agent,
    Status,
    ToolRequest,
    reserve_cost,
    retry_delay,
    safe_path,
    transition,
)


def test_state_machine_terminal_is_immutable():
    transition("QUEUED", Status.RUNNING)
    transition("RUNNING", Status.RETRYING)
    transition("RETRYING", Status.RUNNING)
    transition("RUNNING", Status.COMPLETED)
    for new in Status:
        with pytest.raises(ValueError):
            transition("COMPLETED", new)
    with pytest.raises(ValueError):
        transition("QUEUED", Status.COMPLETED)


@pytest.mark.parametrize(
    "path",
    [
        "../secret.py",
        "/etc/passwd",
        "C:/x.py",
        "a\\b.py",
        "a//b.py",
        "./x.py",
        "x\x00.py",
        ".env.py",
    ],
)
def test_traversal(path):
    with pytest.raises(ValueError):
        safe_path(path)


def test_validation_and_protected_tests():
    with pytest.raises(ValidationError):
        Agent(timeout=-1)
    with pytest.raises(ValidationError):
        Action(operation="shell", content="curl evil")
    with pytest.raises(ValidationError):
        ToolRequest(
            operation_id="a" * 36,
            action=Action(operation="write_file", path="test_stats.py", content=""),
            files={"test_stats.py": ""},
        )


def test_backoff_and_cost():
    assert retry_delay(1, 0.5) == 0.5
    assert retry_delay(100, 1) == 8
    assert reserve_cost(100, 20, 0.5, 2) == 90
