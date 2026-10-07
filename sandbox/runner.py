"""Only runs INSIDE a disposable container. No host execution fallback exists."""

import base64
import json
import os
import selectors
import signal
import subprocess  # nosec B404
import sys
import time
from pathlib import Path, PurePosixPath


def checked_path(name: str) -> Path:
    if (
        not name
        or len(name) > 160
        or "\\" in name
        or ":" in name
        or PurePosixPath(name).is_absolute()
        or not name.endswith(".py")
        or any(part in {"", ".", ".."} or part.startswith(".") for part in name.split("/"))
        or any(ord(char) < 32 for char in name)
    ):
        raise ValueError("Invalid path")
    path = Path("/workspace") / name
    if not path.resolve().is_relative_to(Path("/workspace")):
        raise ValueError("Path outside workspace")
    return path


def run_tests() -> dict:
    # Fixed argv, no shell; the executable resolves to this container's interpreter.
    # Fixed argv inside an isolated container; never executes on the host.
    process = subprocess.Popen(  # nosec B603
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py", "-v"],
        cwd="/workspace",
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    deadline = time.monotonic() + 8
    reason = None
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                reason = "ToolDeadline"
                break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fd, 4096)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                target = buffers[key.data]
                target.extend(chunk[: max(0, 16000 - len(target))])
                if len(target) >= 16000:
                    reason = "OutputLimit"
                    break
            if reason:
                break
    finally:
        selector.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=1)
    return {
        key: bytes(value).decode("utf-8", errors="replace") for key, value in buffers.items()
    } | {"exit_code": process.returncode, "timeout_reason": reason}


def main() -> None:
    started = time.monotonic()
    payload = json.loads(base64.b64decode(sys.argv[1], validate=True))
    files, action = payload["files"], payload["action"]
    if len(files) > 8 or sum(len(value.encode()) for value in files.values()) > 24000:
        raise ValueError("Workspace too large")
    for name, content in files.items():
        path = checked_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    operation = action["operation"]
    result = {"stdout": "", "stderr": "", "exit_code": 0, "timeout_reason": None}
    if operation == "run_tests":
        result.update(run_tests())
    elif operation in {"read_file", "write_file"}:
        name = action["path"]
        if name not in files:
            raise ValueError("File not allowed")
        path = checked_path(name)
        if operation == "read_file":
            result["stdout"] = path.read_text(encoding="utf-8")[:16000]
        else:
            if name != "stats.py" or len(action["content"].encode()) > 12000:
                raise ValueError("Write not allowed")
            path.write_text(action["content"], encoding="utf-8")
            result["stdout"] = "Updated stats.py in the isolated workspace."
    else:
        raise ValueError("Unknown operation")
    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
