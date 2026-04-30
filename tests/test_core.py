import pytest

from shrimp import Scheme, Shrimp
from shrimp.backends import MemoryBackend


def make_shrimp(**kwargs: object) -> Shrimp:
    return Shrimp(backend=MemoryBackend(), **kwargs)  # type: ignore[arg-type]


def test_encode_returns_short_id() -> None:
    s = make_shrimp()
    short = s.encode("user", "f47ac10b-58cc-4372-a567-0e02b2c3d479")
    assert short == "USE_001"


def test_encode_stable_within_scope() -> None:
    s = make_shrimp()
    a = s.encode("user", "uuid-1", scope="sess")
    b = s.encode("user", "uuid-1", scope="sess")
    assert a == b


def test_encode_different_scopes_may_differ() -> None:
    s = make_shrimp()
    a = s.encode("user", "uuid-1", scope="sess-a")
    b = s.encode("user", "uuid-1", scope="sess-b")
    # Both are valid short IDs; counters are per-scope so both = _001
    assert a == b == "USE_001"


def test_decode_roundtrip() -> None:
    s = make_shrimp()
    real = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    short = s.encode("user", real, scope="sess")
    category, decoded = s.decode(short, scope="sess")
    assert category == "user"
    assert decoded == real


def test_decode_unknown_raises() -> None:
    s = make_shrimp()
    with pytest.raises(KeyError):
        s.decode("USR_999", scope="sess")


def test_encode_many_order_preserved() -> None:
    s = make_shrimp()
    ids = ["uuid-a", "uuid-b", "uuid-c"]
    shorts = s.encode_many("order", ids, scope="sess")
    assert len(shorts) == 3
    assert shorts[0] != shorts[1] != shorts[2]


def test_encode_many_deduplicates() -> None:
    s = make_shrimp()
    shorts = s.encode_many("order", ["uuid-x", "uuid-x"], scope="sess")
    assert shorts[0] == shorts[1]


def test_decode_many() -> None:
    s = make_shrimp()
    ids = ["uuid-1", "uuid-2"]
    shorts = s.encode_many("doc", ids, scope="sess")
    results = s.decode_many(shorts, scope="sess")
    assert [r[1] for r in results] == ids


def test_scope_context_manager() -> None:
    s = make_shrimp()
    with s.scope("sess") as scoped:
        short = scoped.encode("user", "uuid-1")
        cat, real = scoped.decode(short)
    assert cat == "user"
    assert real == "uuid-1"


def test_clear_scope() -> None:
    s = make_shrimp()
    short = s.encode("user", "uuid-1", scope="sess")
    s.clear_scope("sess")
    with pytest.raises(KeyError):
        s.decode(short, scope="sess")


def test_custom_scheme_prefix_map() -> None:
    scheme = Scheme(prefix_map={"user": "USR", "order": "ORD"}, counter_format="{:04d}")
    s = Shrimp(backend=MemoryBackend(), scheme=scheme)
    assert s.encode("user", "uuid-1") == "USR_0001"
    assert s.encode("order", "uuid-2") == "ORD_0001"


def test_custom_scheme_aliaser() -> None:
    scheme = Scheme(aliaser=lambda cat, n: f"{cat[:3]}.{n:x}")
    s = Shrimp(backend=MemoryBackend(), scheme=scheme)
    assert s.encode("user", "uuid-1") == "use.1"


def test_scheme_duplicate_prefix_raises() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        Scheme(prefix_map={"user": "X", "order": "X"})


def test_counter_increments_per_category() -> None:
    s = make_shrimp()
    u1 = s.encode("user", "uuid-1", scope="s")
    u2 = s.encode("user", "uuid-2", scope="s")
    o1 = s.encode("order", "uuid-3", scope="s")
    assert u1 == "USE_001"
    assert u2 == "USE_002"
    assert o1 == "ORD_001"
