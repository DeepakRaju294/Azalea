"""Rate limiter for v2 endpoints.

Pluggable backend: in-process dict by default, Redis when configured.

Per-user (authenticated) and per-IP (anonymous) sliding-window counter.
Default policy: 30 requests / 60 seconds / identity (tunable).

Used by /lessons-v2/visual-qa — clicks are cheap on the client but each
one calls the chat LLM. Without a cap a misbehaving page (or a
malicious caller) could rack up cost quickly.

Configuration:
  V2_RATE_LIMIT_BACKEND=memory (default) | redis
  V2_RATE_LIMIT_REDIS_URL=redis://localhost:6379/0
  V2_RATE_LIMIT_MAX_EVENTS=30
  V2_RATE_LIMIT_WINDOW_SECONDS=60
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from typing import Any, Protocol

from fastapi import HTTPException, Request

_logger = logging.getLogger(__name__)


class RateLimiterBackend(Protocol):
    """Abstract storage backend. Implement `check_and_record` to add a
    new transport (Redis, Memcached, etc.).

    Must raise HTTPException(429) when over-limit and atomically record
    the event when under-limit. Thread-safe.
    """

    def check_and_record(self, identity: str) -> None: ...


class _InMemoryBackend:
    """Default backend: in-process dict + lock. Resets on process
    restart. Suitable for single-instance deployments."""

    def __init__(self, max_events: int, window_seconds: int) -> None:
        self._max = max_events
        self._window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, identity: str) -> None:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            events = self._events.get(identity)
            if events is None:
                events = deque()
                self._events[identity] = events
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self._max:
                retry_after = max(1, int(events[0] + self._window - now))
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Rate limit: {self._max} requests per "
                        f"{self._window} seconds. Retry in {retry_after}s."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)


class _RedisBackend:
    """Redis backend using a sorted-set sliding window. Shares state
    across instances. Falls back transparently to the in-memory backend
    if Redis is unreachable at request time.
    """

    def __init__(self, url: str, max_events: int, window_seconds: int) -> None:
        self._max = max_events
        self._window = window_seconds
        # Import lazily so the module loads even when redis isn't installed.
        try:
            import redis  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "V2_RATE_LIMIT_BACKEND=redis requires the `redis` package"
            ) from exc
        self._redis = redis.Redis.from_url(url)
        self._fallback = _InMemoryBackend(max_events, window_seconds)

    def check_and_record(self, identity: str) -> None:
        key = f"v2rl:{identity}"
        now_ms = int(time.time() * 1000)
        cutoff = now_ms - self._window * 1000
        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            pipe.zadd(key, {str(now_ms): now_ms})
            pipe.expire(key, self._window + 1)
            _, count, _, _ = pipe.execute()
            if int(count) >= self._max:
                # Pull the oldest event to compute retry-after
                oldest = self._redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_ms = int(oldest[0][1])
                    retry_after = max(1, (oldest_ms + self._window * 1000 - now_ms) // 1000)
                else:
                    retry_after = self._window
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Rate limit: {self._max} requests per "
                        f"{self._window} seconds. Retry in {retry_after}s."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Redis rate limit failed (%s); using in-memory fallback", exc)
            self._fallback.check_and_record(identity)


def _build_backend() -> RateLimiterBackend:
    max_events = int(os.environ.get("V2_RATE_LIMIT_MAX_EVENTS", "30"))
    window_seconds = int(os.environ.get("V2_RATE_LIMIT_WINDOW_SECONDS", "60"))
    backend = (os.environ.get("V2_RATE_LIMIT_BACKEND") or "memory").lower()
    if backend == "redis":
        url = os.environ.get("V2_RATE_LIMIT_REDIS_URL") or "redis://localhost:6379/0"
        try:
            return _RedisBackend(url, max_events, window_seconds)
        except RuntimeError as exc:
            _logger.warning("Falling back to in-memory rate limiter: %s", exc)
    return _InMemoryBackend(max_events, window_seconds)


_visual_qa_limiter: RateLimiterBackend = _build_backend()
_practice_submit_limiter: RateLimiterBackend = _build_backend()


# Backwards-compat: keep the SlidingWindowLimiter name as a thin shim
# pointing at the in-memory implementation, so any existing import path
# stays valid.
class SlidingWindowLimiter:
    def __init__(self, max_events: int = 30, window_seconds: int = 60) -> None:
        self._impl = _InMemoryBackend(max_events, window_seconds)

    def check(self, identity: str) -> None:
        self._impl.check_and_record(identity)


def visual_qa_identity(request: Request, current_user: dict[str, Any] | None) -> str:
    if current_user and current_user.get("user_id"):
        return f"user:{current_user['user_id']}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def enforce_visual_qa_rate_limit(
    request: Request,
    current_user: dict[str, Any] | None,
) -> None:
    """Call from the visual-qa endpoint; raises 429 if over-limit."""
    _visual_qa_limiter.check_and_record(visual_qa_identity(request, current_user))


def enforce_practice_submit_rate_limit(
    request: Request,
    current_user: dict[str, Any] | None,
) -> None:
    """Call from practice-submit endpoints; raises 429 if over-limit.

    Uses the same backend and default window as visual QA, but keeps a
    separate bucket so normal chat use does not consume practice attempts.
    """
    identity = visual_qa_identity(request, current_user).replace("user:", "practice:user:", 1)
    identity = identity.replace("ip:", "practice:ip:", 1)
    _practice_submit_limiter.check_and_record(identity)
