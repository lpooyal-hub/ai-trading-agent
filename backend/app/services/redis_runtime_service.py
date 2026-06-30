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

    def release_lock(self, lock: RedisLockResult) -> bool:
        if not lock.enabled or not lock.acquired:
            return False
        try:
            if self.client.get(lock.key) != lock.token:
                return False
            return bool(self.client.delete(lock.key))
        except RedisError:
            return False
