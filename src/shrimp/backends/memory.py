from __future__ import annotations

import threading
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shrimp.scheme import Scheme


class MemoryBackend:
    """In-process backend. No persistence across restarts. Safe for tests and single-process use."""

    def __init__(self, scheme: Scheme) -> None:
        self._lock = threading.Lock()
        # {scope: {category: {"fwd": {real_id: short_id}, "rev": {short_id: (category, real_id)}, "counter": int}}}
        self._data: dict[str, dict[str, Any]] = defaultdict(
            lambda: defaultdict(lambda: {"fwd": {}, "rev": {}, "counter": 0})
        )
        self._scheme = scheme

    def _scope_cat(self, scope: str, category: str) -> dict[str, Any]:
        return self._data[scope][category]

    def get_or_create(self, scope: str, category: str, real_id: str) -> tuple[str, bool]:
        with self._lock:
            bucket = self._scope_cat(scope, category)
            if real_id in bucket["fwd"]:
                return bucket["fwd"][real_id], False
            bucket["counter"] += 1
            short_id = self._scheme.make_short_id(category, bucket["counter"])
            bucket["fwd"][real_id] = short_id
            bucket["rev"][short_id] = (category, real_id)
            return short_id, True

    def lookup(self, scope: str, short_id: str) -> tuple[str, str] | None:
        with self._lock:
            for cat_data in self._data.get(scope, {}).values():
                if short_id in cat_data["rev"]:
                    return cat_data["rev"][short_id]
        return None

    def clear_scope(self, scope: str) -> None:
        with self._lock:
            self._data.pop(scope, None)

    def set_ttl(self, scope: str, seconds: int) -> None:
        # Memory backend: schedule scope deletion after TTL
        timer = threading.Timer(seconds, self.clear_scope, args=(scope,))
        timer.daemon = True
        timer.start()
