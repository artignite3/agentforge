"""Vendor-neutral contracts, input limits, and legal run transitions."""

import ast
import math
import random
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Status(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


TERMINAL = {Status.COMPLETED, Status.FAILED, Status.CANCELLED, Status.TIMED_OUT}
TRANSITIONS = {
    Status.QUEUED: {Status.RUNNING, Status.CANCELLED, Status.TIMED_OUT},
    Status.RUNNING: TERMINAL | {Status.RETRYING},
    Status.RETRYING: {Status.RUNNING, Status.CANCELLED, Status.TIMED_OUT, Status.FAILED},
}


def transition(old: str, new: Status) -> None:
    if new not in TRANSITIONS.get(Status(old), set()):
        raise ValueError(f"Illegal transition: {old} -> {new}")


def retry_delay(attempt: int, jitter: float | None = None) -> float:
    """Capped exponential full jitter; callers enforce an attempt ceiling."""
    return min(8.0, 2.0 ** max(0, attempt - 1)) * (
        random.random() if jitter is None else jitter  # nosec B311
    )


def safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or len(value) > 160
        or "\\" in value
        or ":" in value
        or path.is_absolute()
        or any(p in {"", ".", ".."} for p in value.split("/"))
        or any(ord(c) < 32 for c in value)
        or not value.endswith(".py")
        or any(p.startswith(".") for p in path.parts)
    ):
        raise ValueError("Only normalized relative Python paths are allowed")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Agent(StrictModel):
    name: str = Field(
        default="repo-engineer", min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9 _.-]+$"
    )
    version: str = Field(default="v1", min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9._-]+$")
    provider: Literal["demo", "auto", "openai", "gemini"] = "demo"
    instructions: str = Field(
        default="Repair the bug without modifying tests. Verify the fix.", max_length=2000
    )
    timeout: int = Field(default=120, ge=10, le=600)
    budget_usd: float = Field(default=0.20, ge=0, le=5, allow_inf_nan=False)
    max_tokens: int = Field(default=100000, ge=100, le=500000)
    max_steps: int = Field(default=16, ge=2, le=30)


class RunCreate(StrictModel):
    agent_id: str = Field(min_length=36, max_length=36)
    task: str = Field(
        default="Find and repair the bug in the bundled statistics repository.",
        min_length=1,
        max_length=4000,
    )
    fixture: Literal["mean", "clamp"] = "mean"


class Action(StrictModel):
    operation: Literal["read_file", "write_file", "run_tests", "finish"]
    path: str = Field(default="", max_length=160)
    content: str = Field(default="", max_length=12000)
    explanation: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def valid_operation(self) -> "Action":
        if self.operation in {"read_file", "write_file"}:
            safe_path(self.path)
        elif self.path or self.content:
            raise ValueError("Only file operations accept paths or content")
        if self.operation != "write_file" and self.content:
            raise ValueError("Only write_file accepts content")
        return self


class ToolRequest(StrictModel):
    operation_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    action: Action
    files: dict[str, Annotated[str, Field(max_length=12000)]] = Field(max_length=8)

    @field_validator("files")
    @classmethod
    def validate_files(cls, files: dict[str, str]) -> dict[str, str]:
        for path in files:
            safe_path(path)
        if sum(len(v.encode()) for v in files.values()) > 24000:
            raise ValueError("Workspace exceeds 24KB")
        return files

    @model_validator(mode="after")
    def protect_tests(self) -> "ToolRequest":
        if self.action.operation in {"read_file", "write_file"}:
            if self.action.path not in self.files:
                raise ValueError("File is not in the workspace allowlist")
        if self.action.operation == "write_file" and self.action.path != "stats.py":
            raise ValueError("Only stats.py may be modified")
        if self.action.operation == "finish":
            raise ValueError("finish is not a tool")
        return self


class ToolResult(StrictModel):
    stdout: str = Field(default="", max_length=16000)
    stderr: str = Field(default="", max_length=16000)
    exit_code: int
    duration_ms: int = Field(ge=0)
    timeout_reason: str | None = None


class Generation(StrictModel):
    action: Action
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


def reserve_cost(input_bound: int, output_bound: int, input_rate: float, output_rate: float) -> int:
    return math.ceil(input_bound * input_rate + output_bound * output_rate)


# Names that let fixture source escape its role as plain arithmetic: process exit, dynamic
# code, reflection, I/O, or test-framework tampering. A heuristic for the bundled fixtures,
# not a general sandbox; container isolation remains the security boundary.
_FORBIDDEN_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "exit",
        "getattr",
        "globals",
        "input",
        "locals",
        "open",
        "quit",
        "setattr",
        "vars",
    }
)
_ALLOWED_IMPORTS = frozenset({"math"})


def source_policy_error(source: str) -> str | None:
    """Reject fixture source that could fake a test result instead of computing one."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None  # Let the tests report the syntax error as an ordinary observation.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {(node.module or "").split(".")[0]}
        else:
            names = set()
        if names - _ALLOWED_IMPORTS:
            return "Only the math module may be imported by stats.py"
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            return f"stats.py may not reference {node.id}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return "stats.py may not access dunder attributes"
    return None


def action_policy_error(action: Action, files: dict[str, str]) -> str | None:
    """Explain a disallowed tool action so the planner can correct it on the next step."""
    if action.operation in {"read_file", "write_file"} and action.path not in files:
        return f"{action.path} is not in the workspace; available files: {', '.join(sorted(files))}"
    if action.operation == "write_file":
        if action.path != "stats.py":
            return "Only stats.py may be modified; tests are read-only"
        return source_policy_error(action.content)
    return None


def tests_verified(result: ToolResult, expected_tests: int) -> bool:
    """Require a clean exit AND unittest's own summary for the trusted fixture's test count."""
    summary = result.stderr.rstrip().splitlines()
    return (
        result.exit_code == 0
        and result.timeout_reason is None
        and bool(summary)
        and summary[-1].strip() == "OK"
        and f"Ran {expected_tests} test" in result.stderr
    )
