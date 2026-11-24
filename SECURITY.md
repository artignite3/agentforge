# Security model

AgentForge is a portfolio-oriented production baseline for an operator-controlled workspace. It is not a hostile multi-tenant code-execution platform. Report vulnerabilities privately to the repository owner; do not include live credentials in issues or traces.

## Trust boundaries

| Input/actor | Trust | Primary defenses | Residual limitation |
|---|---|---|---|
| Internet HTTP client | Untrusted | Bearer auth, body caps, Pydantic bounds, Redis limits, active-run admission | Edge connection/DDoS protection remains a deployment responsibility |
| Task/model output | Untrusted | Strict Action schema; fixed operations; file allowlist; no shell interpolation | A model can still produce an incorrect repair |
| Repository source/tool output | Untrusted | Disposable non-root container, output caps, text-only rendering | A source policy blocks the obvious ways to fake a pass, but code in the test process can still influence its result |
| API/worker | Trusted application components | No Docker socket; owner-scoped queries; fenced transactions | Compromise can access model credentials and application DB |
| Sandbox gateway | Highly trusted | Private network, distinct key, fixed image/argv/options, bounded concurrency | Docker socket access gives broad daemon control if gateway is compromised |
| Docker daemon/host kernel | Trusted infrastructure | Resource limits, namespaces, dropped capabilities | Shared-kernel containers are not a hardened multi-tenant boundary |
| Database backups | Sensitive | Operator access controls and encrypted backup policy | Source snapshots/traces may contain private project data in future extensions |

## Implemented controls

- Keys are generated with `secrets.token_urlsafe` (user keys carry an `afk_` prefix for secret scanners); the bootstrap and gateway keys must be at least 32 characters. Only SHA-256 hashes of API keys are stored, which is appropriate for high-entropy generated keys. Keys have `read` / `submit` / `admin` roles, optional expiry, and revocation that takes effect within five seconds; the bootstrap key cannot be revoked through the API and is rotated through the environment without orphaning data. The gateway key is compared in constant time.
- Secrets come from environment/.env; `.env` is ignored by Git and Docker build contexts. No frontend build variable contains a key. The UI stores its key in memory, never localStorage, sessionStorage, URLs, or screenshots.
- Every data API requires authentication. Liveness, readiness, and the OpenAPI schema are intentionally public and return limited information. Interactive `/docs` and `/redoc` are disabled in production because they load third-party scripts that the dashboard CSP blocks. Production startup requires PostgreSQL, HTTPS CORS origins, Redis for the API, and sufficiently long keys for the processes that use them. Wildcard CORS is forbidden in every environment.
- A body middleware measures received bytes before JSON parsing, including chunked bodies. Default limit is 64KB. Schema fields bound task text, source length, file count, steps, runtime, and spend. Reverse proxy request/body deadlines address slow clients; the app alone does not solve slowloris attacks.
- Redis applies an atomic fixed-window limit per authenticated key, with a separate bounded bucket for invalid credentials keyed on the hashed socket peer. With `AGENTFORGE_TRUSTED_PROXY_HOPS` (production Compose sets 2: Caddy, then nginx) the client address is taken from the `X-Forwarded-For` entry recorded by the outermost trusted proxy; Caddy discards client-supplied forwarding headers, so a client cannot choose its own bucket. With 0 the socket peer is used. The development fallback is process-local only. Redis errors fail closed. Active runs are capped under a per-owner database lock.
- SQLAlchemy parameterizes user values. User fields are never concatenated into SQL. The PostgreSQL test's schema name is generated internally from a UUID and is not user controlled.
- Only normalized relative `.py` paths are accepted. Absolute paths, drive prefixes, backslashes, parent/dot components, hidden components, control characters, missing allowlist entries, and extra JSON fields are rejected. Only `stats.py` is writable. Tests are supplied from the saved fixture.
- There are no arbitrary Git clone, URL fetch, host file, shell, package installation, or model-selected executable operations. Provider endpoints are fixed HTTPS origins. Redirects and proxy environment inheritance are disabled for provider requests. No API input controls upstream destinations.
- Tool containers run as UID/GID 10001, with no network, no capabilities, `no-new-privileges`, no host mounts, no Docker socket, a read-only root, and private size-limited tmpfs workspaces.
- Each tool container gets 128MiB RAM and equal swap cap, 0.5 CPU, 32 PIDs, an eight-second test deadline and twelve-second outer deadline. stdout/stderr are independently capped at 16KB, Docker logs are capped, and the gateway bounds concurrent execution to two containers.
- Commands use fixed structured argv with no `shell=True`. Base64 task input is an argv value, not shell syntax. The runner is executed only in the tool image. The API/worker have no direct code-execution fallback.
- The gateway removes its container in `finally` and periodically reaps only expired containers carrying its label/name prefix. Cancelling a run fences commits immediately; remote work may continue until its strict deadline.
- Application logs use an allowlist and omit task/model/tool text, headers, secrets, URLs, and exception messages. Request logs carry method, route template, status, duration, and the acting credential id. Containers rotate logs at 10 MB × 5. API errors hide raw Pydantic inputs and unexpected exception details. Debug mode is off. Trace data is intentionally visible only to the authenticated owner.
- React renders source/output as text. nginx applies `nosniff`, frame denial, a restricted CSP, and no-referrer. The CSP permits inline styles for UI layout; it permits no inline script or external script origins.
- CI includes Bandit, pip-audit, npm audit, type checking, critical-path tests, real isolation checks, and image builds. Dependency audit success describes the audit date, not permanent vulnerability freedom. Container OS package scanning is a documented additional production task.

## Prompt injection and tool-result integrity

The system prompt marks tasks, files, and tool output as untrusted, but a prompt is not a security boundary. The boundary is the independent gateway policy and container isolation. A malicious model cannot request host commands, add network access, mount paths, alter Docker options, or write outside the source allowlist through the API.

The source itself executes inside the test process. Before execution, a write to `stats.py` is rejected if it imports anything but `math`, references process-exit, dynamic-code, I/O, or reflection builtins, or accesses dunder attributes; a pass also requires unittest's own summary to report the fixture's trusted test count and `OK`. This blocks the obvious ways to fake a pass (`os._exit(0)`, patching `unittest`), but it is a heuristic for these fixtures, not a sandbox: code inside the test process could still influence what it reports. Tests passing are a regression signal for the trusted bundled workload, not cryptographic attestation or proof of correctness for adversarial code. Tool output is never interpreted as a new capability grant. Stronger verification would run trusted tests in a separate protected supervisor/protocol and add semantic checks.

## Before internet exposure

1. Use a dedicated host or separate sandbox host with patched Docker/kernel. Prefer rootless Docker where resource controls are supported and verified; its socket path/group needs explicit configuration. Never expose the Docker TCP API.
2. Keep PostgreSQL, Redis, worker, and gateway private. The Compose networks enforce this: `data`, `cache`, and `tools` are internal; only the frontend joins the edge network; only the worker has egress. Run `scripts/deploy_check.py` after any Compose change.
3. Issue a separate least-role key per person or integration and keep the bootstrap key for administration. Configure provider-side spend caps. Provider and gateway keys reach only the worker; the API never receives them.
4. Apply migrations deliberately; maintain encrypted backups and test restoration. Add an operator retention policy for runs/checkpoints/output.
5. Add edge abuse protection, monitoring, patched image digests, and container vulnerability scanning. Test UID/cgroup/network restrictions on the target host.

## Known limitations

One owner (workspace) per deployment, with role-scoped keys but no SSO, MFA, or per-key IP restrictions; Redis has no password (it is reachable only from the API on an internal network); only the edge image is pinned by digest and images are not scanned in CI; no mTLS between internal services, no encrypted application-level snapshots, no secret-detection filter for arbitrary future repositories, no host attestation, no microVM boundary, no provider billing reconciliation, no distributed circuit breaker, retention that must be scheduled by the operator, and no formal penetration test. Fixed-window rate limits allow boundary bursts. Docker socket exposure is restricted to the gateway but remains a significant trust assumption. These limitations must remain visible in interviews and deployment claims.
