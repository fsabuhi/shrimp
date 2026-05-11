from __future__ import annotations

from typing import TYPE_CHECKING, Any

import redis as redis_lib

if TYPE_CHECKING:
    from shrimp.scheme import Scheme

# Two-phase atomic encode:
# Phase 1 (Python): INCR counter → n, format short_id via scheme.
# Phase 2 (Lua): HSETNX fwd[real_id]=short_id. If another caller already set it (race),
#   return their winner. If we won, also write rev. Gap in counter is acceptable.
_LUA_HSETNX_AND_REV = """
local existing = redis.call('HGET', KEYS[1], ARGV[1])
if existing then
    return {existing, '0'}
end
local won = redis.call('HSETNX', KEYS[1], ARGV[1], ARGV[3])
if won == 0 then
    return {redis.call('HGET', KEYS[1], ARGV[1]), '0'}
end
redis.call('HSET', KEYS[2], ARGV[3], ARGV[2])
return {ARGV[3], '1'}
"""


class RedisBackend:
    def __init__(
        self, scheme: Scheme, url: str = "redis://localhost:6379", key_prefix: str = "shrimp"
    ) -> None:
        self._client = redis_lib.Redis.from_url(url, decode_responses=True)
        self._prefix = key_prefix
        self._script = self._client.register_script(_LUA_HSETNX_AND_REV)
        self._scheme = scheme

    def _keys(self, scope: str, category: str) -> tuple[str, str, str]:
        p = f"{self._prefix}:{scope}:{category}"
        return f"{p}:fwd", f"{p}:rev", f"{p}:counter"

    def get_or_create(self, scope: str, category: str, real_id: str) -> tuple[str, bool]:
        fwd, rev, counter = self._keys(scope, category)
        # Fast path: already encoded
        existing = self._client.hget(fwd, real_id)
        if existing:
            return existing, False
        # Claim a counter slot, format short_id, then atomically set via Lua
        n = self._client.incr(counter)
        short_id = self._scheme.make_short_id(category, n)
        rev_val = f"{category}:{real_id}"
        result = self._script(keys=[fwd, rev, counter], args=[real_id, rev_val, short_id])  # type: ignore[arg-type]
        winner, created_flag = result
        return winner, created_flag == "1"

    def lookup(self, scope: str, short_id: str) -> tuple[str, str] | None:
        pattern = f"{self._prefix}:{scope}:*:rev"
        for key in self._client.scan_iter(pattern):
            val = self._client.hget(key, short_id)
            if val:
                category, real_id = val.split(":", 1)
                return category, real_id
        return None

    def clear_scope(self, scope: str) -> None:
        pattern = f"{self._prefix}:{scope}:*"
        keys = list(self._client.scan_iter(pattern))
        if keys:
            self._client.delete(*keys)

    def set_ttl(self, scope: str, seconds: int) -> None:
        pattern = f"{self._prefix}:{scope}:*"
        for key in self._client.scan_iter(pattern):
            self._client.expire(key, seconds)
