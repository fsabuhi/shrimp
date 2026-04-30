from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from shrimp.backends import Backend, MemoryBackend, RedisBackend
from shrimp.scheme import Scheme


class ScopedShrimp:
    """Shrimp pre-bound to a scope. Returned by `shrimp.scope()`."""

    def __init__(self, shrimp: "Shrimp", scope: str) -> None:
        self._shrimp = shrimp
        self._scope = scope

    def encode(self, category: str, real_id: str) -> str:
        return self._shrimp.encode(category, real_id, scope=self._scope)

    def decode(self, short_id: str) -> tuple[str, str]:
        return self._shrimp.decode(short_id, scope=self._scope)

    def encode_many(self, category: str, real_ids: list[str]) -> list[str]:
        return self._shrimp.encode_many(category, real_ids, scope=self._scope)

    def decode_many(self, short_ids: list[str]) -> list[tuple[str, str]]:
        return self._shrimp.decode_many(short_ids, scope=self._scope)


class Shrimp:
    def __init__(
        self,
        *,
        redis_url: str | None = None,
        backend: Backend | None = None,
        scheme: Scheme | None = None,
    ) -> None:
        self._scheme = scheme or Scheme()
        if backend is not None:
            self._backend = backend
        elif redis_url is not None:
            self._backend = RedisBackend(url=redis_url)
        else:
            self._backend = MemoryBackend()
        # Inject scheme into backend so it can format short IDs
        self._backend._scheme = self._scheme  # type: ignore[union-attr]

    def encode(self, category: str, real_id: str, *, scope: str = "default") -> str:
        short_id, _ = self._backend.get_or_create(scope, category, real_id)
        return short_id

    def decode(self, short_id: str, *, scope: str = "default") -> tuple[str, str]:
        result = self._backend.lookup(scope, short_id)
        if result is None:
            raise KeyError(f"Unknown short ID {short_id!r} in scope {scope!r}")
        return result

    def encode_many(
        self, category: str, real_ids: list[str], *, scope: str = "default"
    ) -> list[str]:
        seen: dict[str, str] = {}
        out: list[str] = []
        for real_id in real_ids:
            if real_id not in seen:
                seen[real_id] = self.encode(category, real_id, scope=scope)
            out.append(seen[real_id])
        return out

    def decode_many(
        self, short_ids: list[str], *, scope: str = "default"
    ) -> list[tuple[str, str]]:
        return [self.decode(sid, scope=scope) for sid in short_ids]

    @contextmanager
    def scope(self, scope_id: str) -> Generator[ScopedShrimp, None, None]:
        yield ScopedShrimp(self, scope_id)

    def create_scope(self, scope_id: str, *, ttl_seconds: int | None = None) -> None:
        if ttl_seconds is not None:
            self._backend.set_ttl(scope_id, ttl_seconds)

    def clear_scope(self, scope_id: str) -> None:
        self._backend.clear_scope(scope_id)
