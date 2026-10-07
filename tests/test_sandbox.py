import os

import pytest

from agentforge.domain import Action, ToolRequest
from agentforge.fixtures import repository
from agentforge.models import uid
from agentforge.sandbox import DockerExecutor, container_options


def test_container_security_controls():
    request = ToolRequest(
        operation_id=uid(), action=Action(operation="run_tests"), files=repository("mean")
    )
    options = container_options(request, "agentforge-tool:local")
    assert options["network_disabled"] is True
    assert options["read_only"] is True
    assert options["user"] == "10001:10001"
    assert options["cap_drop"] == ["ALL"]
    assert options["pids_limit"] == 32
    assert "volumes" not in options
    assert options["nano_cpus"] == 500_000_000
    assert options["security_opt"] == ["no-new-privileges:true"]
    assert "API_KEY" not in str(options["environment"])


@pytest.mark.docker
@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1", reason="Set RUN_DOCKER_TESTS=1 for real container tests"
)
def test_real_container_failure_repair_and_network_isolation():
    executor = DockerExecutor("agentforge-tool:local")
    files = repository("mean")
    failed = executor.execute(
        ToolRequest(operation_id=uid(), action=Action(operation="run_tests"), files=files)
    )
    assert failed.exit_code != 0 and "FAILED" in failed.stderr
    files["stats.py"] = files["stats.py"].replace("(len(values) + 1)", "len(values)")
    success = executor.execute(
        ToolRequest(operation_id=uid(), action=Action(operation="run_tests"), files=files)
    )
    assert success.exit_code == 0 and "OK" in success.stderr
    files["test_stats.py"] = (
        "import socket, unittest, os\nclass Isolation(unittest.TestCase):\n def test_isolation(self):\n  self.assertNotEqual(os.getuid(), 0)\n  self.assertFalse(os.path.exists('/var/run/docker.sock'))\n  with self.assertRaises(OSError): socket.create_connection(('1.1.1.1', 443), timeout=1)\n  with self.assertRaises(OSError): open('/cannot-write', 'w')\n"
    )
    isolated = executor.execute(
        ToolRequest(operation_id=uid(), action=Action(operation="run_tests"), files=files)
    )
    assert isolated.exit_code == 0, isolated


@pytest.mark.docker
@pytest.mark.skipif(os.getenv("RUN_DOCKER_TESTS") != "1", reason="Set RUN_DOCKER_TESTS=1")
def test_tool_timeout_and_output_limits():
    executor = DockerExecutor("agentforge-tool:local")
    files = {"test_loop.py": "while True: pass\n"}
    timeout = executor.execute(
        ToolRequest(operation_id=uid(), action=Action(operation="run_tests"), files=files)
    )
    assert timeout.timeout_reason in {"ToolDeadline", "ContainerDeadline"}
    files = {"test_output.py": "print('a' * 1000000)\n"}
    output = executor.execute(
        ToolRequest(operation_id=uid(), action=Action(operation="run_tests"), files=files)
    )
    assert output.timeout_reason == "OutputLimit"
