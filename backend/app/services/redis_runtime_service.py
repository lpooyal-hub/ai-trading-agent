from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.config import Settings, get_settings

try:
    from redis import Redis
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - keeps local dev usable before dependency install.
    Redis = None
    RedisError = Exception


@dataclass
class RedisLockResult:
    key: str
    token: str
    acquired: bool
    enabled: bool
    reason: str


class RedisRuntimeService:
    agent_run_lock_key = "agent:run_once:lock"

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: Redis | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.redis_enabled and self.settings.redis_url and Redis is not None)

    def status(self) -> dict:
        if not self.settings.redis_enabled:
            return {
                "enabled": False,
                "available": False,
                "reason": "REDIS_ENABLED is false.",
            }
        if not self.settings.redis_url:
            return {
                "enabled": True,
                "available": False,
                "reason": "REDIS_URL is not configured.",
            }
        if Redis is None:
            return {
                "enabled": True,
                "available": False,
                "reason": "redis package is not installed.",
            }
        try:
            self.client.ping()
        except RedisError as exc:
            return {
                "enabled": True,
                "available": False,
                "reason": f"Redis connection failed: {exc}",
            }
        return {
            "enabled": True,
            "available": True,
            "reason": "Redis runtime is available.",
        }

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._client

    def acquire_agent_run_lock(self) -> RedisLockResult:
        token = str(uuid4())
        if not self.settings.redis_enabled:
            return RedisLockResult(
                key=self.agent_run_lock_key,
                token=token,
                acquired=True,
                enabled=False,
                reason="Redis lock is disabled.",
            )
        if not self.enabled:
            return RedisLockResult(
                key=self.agent_run_lock_key,
                token=token,
                acquired=True,
                enabled=False,
                reason=self.status()["reason"],
            )
        try:
            acquired = bool(
                self.client.set(
                    self.agent_run_lock_key,
                    token,
                    nx=True,
                    ex=self.settings.redis_agent_run_lock_ttl_seconds,
                )
            )
        except RedisError as exc:
            return RedisLockResult(
                key=self.agent_run_lock_key,
                token=token,
                acquired=True,
                enabled=False,
                reason=f"Redis lock unavailable, continuing without lock: {exc}",
            )

        if not acquired:
            return RedisLockResult(
                key=self.agent_run_lock_key,
                token=token,
                acquired=False,
                enabled=True,
                reason="Another agent run is already in progress.",
            )
        return RedisLockResult(
            key=self.agent_run_lock_key,
            token=token,
            acquired=True,
            enabled=True,
            reason="Redis agent run lock acquired.",
        )

    def renew_agent_run_lock(self, lock: RedisLockResult, ttl_seconds: int) -> RedisLockResult:
        """Extend a held lock's TTL for one more cycle of a continuous session.

        Only renews if we still own it (token matches) so a session never keeps
        running once the lock has been taken by someone else. Not atomic (GET then
        EXPIRE), matching the existing release_lock() pattern in this file; a lost
        race here just means the next loop_gate check stops the session, which is
        the safe failure mode.
        """
        if not lock.enabled or not lock.acquired:
            return lock
        try:
            if self.client.get(lock.key) != lock.token:
                return RedisLockResult(
                    key=lock.key,
                    token=lock.token,
                    acquired=False,
                    enabled=True,
                    reason="Agent run lock was lost (held by another process).",
                )
            self.client.expire(lock.key, ttl_seconds)
            return RedisLockResult(
                key=lock.key,
                token=lock.token,
                acquired=True,
                enabled=True,
                reason="Agent run lock renewed.",
            )
        except RedisError as exc:
            return RedisLockResult(
                key=lock.key,
                token=lock.token,
                acquired=False,
                enabled=True,
                reason=f"Agent run lock renewal failed: {exc}",
            )

    def release_lock(self, lock: RedisLockResult) -> bool:
        if not lock.enabled or not lock.acquired:
            return False
        try:
            if self.client.get(lock.key) != lock.token:
                return False
            return bool(self.client.delete(lock.key))
        except RedisError:
            return False
