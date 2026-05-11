from __future__ import annotations

import copy
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

from shrimp.backends import Backend, MemoryBackend
from shrimp.scheme import Scheme


@dataclass
class ResolveResult:
    """Result of resolving short IDs in text back to real IDs."""

    resolved: str
    unknown_ids: list[str] = field(default_factory=list)
    stats: dict[str, int | float] = field(default_factory=dict)


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

    def render(self, data: Any, fields: dict[str, str]) -> Any:
        return self._shrimp.render(data, fields, scope=self._scope)

    def resolve(self, text: str) -> ResolveResult:
        return self._shrimp.resolve(text, scope=self._scope)


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
            try:
                from shrimp.backends.redis import RedisBackend
            except ImportError as exc:
                raise ImportError(
                    "redis is required for RedisBackend. "
                    "Install it with: pip install shrimp-llm[redis]"
                ) from exc
            self._backend = RedisBackend(scheme=self._scheme, url=redis_url)
        else:
            self._backend = MemoryBackend(scheme=self._scheme)

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

    # -- render -----------------------------------------------------------------

    def render(
        self, data: Any, fields: dict[str, str], *, scope: str = "default"
    ) -> Any:
        """Deep-copy *data* and replace fields matching dot-paths with short IDs."""
        out = copy.deepcopy(data)
        for path, category in fields.items():
            parts = path.split(".")
            self._walk(out, parts, 0, category, scope)
        return out

    def _walk(
        self, obj: Any, parts: list[str], idx: int, category: str, scope: str
    ) -> None:
        if idx >= len(parts):
            return
        key = parts[idx]
        if key == "[]":
            if isinstance(obj, list):
                for item in obj:
                    self._walk(item, parts, idx + 1, category, scope)
            return
        if idx == len(parts) - 1:
            # Leaf — replace the value
            if isinstance(obj, dict) and key in obj:
                obj[key] = self.encode(category, str(obj[key]), scope=scope)
        else:
            if isinstance(obj, dict) and key in obj:
                self._walk(obj[key], parts, idx + 1, category, scope)

    # -- resolve ----------------------------------------------------------------

    def resolve(self, text: str, *, scope: str = "default") -> ResolveResult:
        """Scan *text* for short-ID patterns, replace with real IDs."""
        pattern = re.compile(r"\b[A-Za-z]{2,}[_\-][A-Za-z0-9]+\b")
        resolved_count = 0
        hallucinated_count = 0
        unknown_ids: list[str] = []

        def _replacer(match: re.Match[str]) -> str:
            nonlocal resolved_count, hallucinated_count
            token = match.group(0)
            result = self._backend.lookup(scope, token)
            if result is not None:
                resolved_count += 1
                return result[1]  # real_id
            hallucinated_count += 1
            unknown_ids.append(token)
            return token

        resolved_text = pattern.sub(_replacer, text)
        total = resolved_count + hallucinated_count
        rate = hallucinated_count / total if total else 0.0
        return ResolveResult(
            resolved=resolved_text,
            unknown_ids=unknown_ids,
            stats={"resolved": resolved_count, "hallucinated": hallucinated_count, "rate": rate},
        )
