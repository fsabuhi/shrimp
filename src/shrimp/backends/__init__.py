from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Backend(Protocol):
    def get_or_create(self, scope: str, category: str, real_id: str) -> tuple[str, bool]:
        """Return (short_id, created). created=True if new mapping was made."""
        ...

    def lookup(self, scope: str, short_id: str) -> tuple[str, str] | None:
        """Return (category, real_id) or None if not found."""
        ...

    def clear_scope(self, scope: str) -> None: ...

    def set_ttl(self, scope: str, seconds: int) -> None: ...


from shrimp.backends.memory import MemoryBackend
from shrimp.backends.redis import RedisBackend

__all__ = ["Backend", "MemoryBackend", "RedisBackend"]
