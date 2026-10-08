"""Check the real HTTPS edge and optionally execute a sandboxed demo run."""

import argparse
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from agentforge import Agent, AgentForge


def verify(url: str, key: str, *, run_demo: bool = False) -> None:
    with httpx.Client(base_url=url, timeout=15, follow_redirects=False, trust_env=False) as client:
        for path in ("/", "/api/health", "/api/ready"):
            response = client.get(path)
            if response.status_code != 200:
                raise ValueError("Frontend or API readiness check failed")
            if url.startswith("https://") and "max-age=" not in response.headers.get(
                "strict-transport-security", ""
            ):
                raise ValueError("HTTPS edge is missing HSTS")
        if client.get("/api/v1/runs").status_code != 401:
            raise ValueError("Unauthenticated data access was not rejected")
        response = client.get("/api/v1/system", headers={"Authorization": f"Bearer {key}"})
        if response.status_code != 200:
            raise ValueError("Authenticated system check failed")
        system = response.json()
        if system.get("environment") != "production" or not system.get("sandbox_ready"):
            raise ValueError("Production configuration or sandbox readiness failed")
    print("PASS: frontend, readiness, authentication, production mode, sandbox probe")
    if run_demo:
        with AgentForge(api_key=key, base_url=url + "/api") as client:
            run = client.run(
                agent=Agent(name="release-smoke", provider="demo"),
                task="Repair the failing repository and verify the original regression tests.",
            )
            completed = client.wait(run["id"], timeout=150)
            trace = client.trace(run["id"])
            if (
                completed["status"] != "COMPLETED"
                or not trace["checkpoint"]["payload"]["tests_passed"]
            ):
                raise ValueError("Sandboxed release workload failed")
            print(f"PASS: sandboxed repair completed; run {run['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="https://your-hostname (without /api)")
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--run-demo", action="store_true")
    parser.add_argument("--allow-local-http", action="store_true")
    args = parser.parse_args()
    url = args.url.rstrip("/")
    parsed = urlsplit(url)
    local_http = (
        args.allow_local_http
        and parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    )
    if (
        (parsed.scheme != "https" and not local_http)
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        parser.error("Use an HTTPS origin; HTTP is allowed only for explicit localhost testing")
    try:
        values = dict(
            line.split("=", 1)
            for line in args.env_file.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        key = values["AGENTFORGE_API_KEY"]
        if len(key) < 32:
            raise ValueError("Missing or invalid API key")
        verify(url, key, run_demo=args.run_demo)
    except (OSError, ValueError, KeyError, httpx.HTTPError, TimeoutError) as exc:
        parser.exit(
            1,
            f"Release check failed ({type(exc).__name__}). Inspect host status privately; no secrets printed.\n",
        )


if __name__ == "__main__":
    main()
