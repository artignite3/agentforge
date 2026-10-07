import asyncio
import hashlib
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import HTTPException, Request
from redis.asyncio import Redis
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agentforge.config import Settings


def owner_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


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


def authentication(settings: Settings, limiter: Limiter) -> Callable[[Request], Awaitable[str]]:
    expected = settings.api_key.get_secret_value()

    async def authenticate(request: Request) -> str:
        header = request.headers.get("Authorization", "")
        supplied = header.removeprefix("Bearer ") if header.startswith("Bearer ") else ""
        if not secrets.compare_digest(supplied.encode(), expected.encode()):
            # Hash the socket peer; never trust unconfigured forwarded headers.
            peer = request.client.host if request.client else "unknown"
            await limiter.check("unauth:" + owner_id(peer))
            raise HTTPException(401, "Invalid API key", headers={"WWW-Authenticate": "Bearer"})
        owner = owner_id(expected)
        await limiter.check(owner)
        return owner

    return authenticate
