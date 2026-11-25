import asyncio
import hashlib
import ipaddress
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, NoReturn, Protocol, cast

from fastapi import HTTPException, Request
from redis.asyncio import Redis
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agentforge.config import Settings

Role = Literal["read", "submit", "admin"]
ROLE_RANK: dict[str, int] = {"read": 0, "submit": 1, "admin": 2}
KEY_PREFIX = "afk_"


def key_hash(key: str) -> str:
    """SHA-256 is appropriate for high-entropy generated keys (not for passwords)."""
    return hashlib.sha256(key.encode()).hexdigest()


# Historical name: an owner created by the bootstrap key has id == key_hash(bootstrap key).
owner_id = key_hash


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(36)


@dataclass(frozen=True)
class Principal:
    owner: str
    credential_id: str
    label: str
    role: str
    expires_at: float | None = None

    def allows(self, role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[role]


class CredentialLookup(Protocol):
    async def principal(self, digest: str) -> Principal | None: ...


def client_ip(request: Request, trusted_hops: int) -> str:
    """Socket peer, or the address recorded by the outermost of `trusted_hops` proxies."""
    peer = request.client.host if request.client else "unknown"
    if trusted_hops <= 0:
        return peer
    hops = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(hops) < trusted_hops:
        return peer
    candidate = hops[-trusted_hops]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return peer


class BodyLimit:
    """Limit bytes actually received, including chunked bodies; enforce before parsing."""

    def __init__(self, app: ASGIApp, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        messages: list[Message] = []
        size = 0
        deadline = time.monotonic() + 10
        while True:
            try:
                message = await asyncio.wait_for(
                    receive(), timeout=max(0, deadline - time.monotonic())
                )
            except TimeoutError:
                await JSONResponse({"detail": "Request body timeout"}, status_code=408)(
                    scope, receive, send
                )
                return
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.limit or len(messages) >= 1024:
                await JSONResponse({"detail": "Request body exceeds limit"}, status_code=413)(
                    scope, receive, send
                )
                return
            messages.append(message)
            if not message.get("more_body", False):
                break
        index = 0

        async def replay() -> Message:
            nonlocal index
            if index < len(messages):
                result = messages[index]
                index += 1
                return result
            return await receive()

        await self.app(scope, replay, send)


class Limiter:
    def __init__(self, settings: Settings):
        self.limit = settings.rate_limit
        self.redis: Redis | None = (
            Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
            if settings.redis_url
            else None
        )
        self.local: dict[str, tuple[int, int]] = {}

    async def check(self, key: str) -> None:
        minute = int(time.time() // 60)
        if self.redis:
            try:
                count = await cast(
                    Awaitable[int],
                    self.redis.eval(
                        "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],120) end; return n",
                        1,
                        f"af:rate:{key}:{minute}",
                    ),
                )
            except Exception as exc:
                raise HTTPException(503, "Rate limiter unavailable") from exc
        else:
            if len(self.local) > 4096:
                self.local = {k: v for k, v in self.local.items() if v[0] == minute}
                if len(self.local) > 4096:
                    raise HTTPException(429, "Rate limit capacity reached")
            previous, count = self.local.get(key, (minute, 0))
            count = count + 1 if previous == minute else 1
            self.local[key] = (minute, count)
        if count > self.limit:
            raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": "60"})


class PrincipalCache:
    """Short-lived cache of *valid* credentials so each request needs no credential query.

    Revocation and expiry take effect within `ttl` seconds in every API process. Unknown
    keys are never cached: random keys must not be able to evict real ones.
    """

    def __init__(self, ttl: float = 5.0, size: int = 1024):
        self.ttl, self.size = ttl, size
        self.entries: dict[str, tuple[float, Principal | None]] = {}

    def cached(self, digest: str) -> Principal | None:
        entry = self.entries.get(digest)
        if entry is None or entry[0] <= time.monotonic():
            return None
        return entry[1]

    async def get(
        self,
        digest: str,
        lookup: CredentialLookup,
        before_lookup: Callable[[], Awaitable[None]] | None = None,
    ) -> Principal | None:
        principal = self.cached(digest)
        if principal is None:
            if before_lookup is not None:
                await before_lookup()  # Admission control before any database work.
            principal = await lookup.principal(digest)
            if principal is not None:
                if len(self.entries) >= self.size:
                    self.entries.clear()
                self.entries[digest] = (time.monotonic() + self.ttl, principal)
        if principal and principal.expires_at is not None and principal.expires_at <= time.time():
            return None
        return principal

    def clear(self) -> None:
        self.entries.clear()


def authentication(
    settings: Settings, limiter: Limiter, lookup: CredentialLookup, cache: PrincipalCache
) -> Callable[[Role], Callable[[Request], Awaitable[Principal]]]:
    def client_bucket(request: Request, kind: str) -> str:
        # Hash the client address so raw IPs never become Redis keys.
        return f"{kind}:" + key_hash(client_ip(request, settings.trusted_proxy_hops))

    async def unauthorized(request: Request) -> NoReturn:
        await limiter.check(client_bucket(request, "unauth"))
        raise HTTPException(401, "Invalid API key", headers={"WWW-Authenticate": "Bearer"})

    def require(role: Role) -> Callable[[Request], Awaitable[Principal]]:
        async def authenticate(request: Request) -> Principal:
            header = request.headers.get("Authorization", "")
            supplied = header.removeprefix("Bearer ") if header.startswith("Bearer ") else ""
            if len(supplied) < 32 or len(supplied) > 256:
                await unauthorized(request)
            # Uncached keys cost a database query, so each client's lookups are rate limited
            # *before* the query; valid keys are cached and rarely reach this path.
            principal = await cache.get(
                key_hash(supplied),
                lookup,
                lambda: limiter.check(client_bucket(request, "lookup")),
            )
            if principal is None:
                await unauthorized(request)
            await limiter.check(principal.credential_id)
            request.state.actor = principal.credential_id
            if not principal.allows(role):
                raise HTTPException(403, f"This key's role does not permit {role} operations")
            return principal

        return authenticate

    return require
