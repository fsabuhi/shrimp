import pytest

from shrimp import ResolveResult, Scheme, Shrimp
from shrimp.backends import MemoryBackend


def make_shrimp(**kwargs: object) -> Shrimp:
    return Shrimp(backend=MemoryBackend(scheme=Scheme()), **kwargs)  # type: ignore[arg-type]


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
    s = Shrimp(backend=MemoryBackend(scheme=scheme), scheme=scheme)
    assert s.encode("user", "uuid-1") == "USR_0001"
    assert s.encode("order", "uuid-2") == "ORD_0001"


def test_custom_scheme_aliaser() -> None:
    scheme = Scheme(aliaser=lambda cat, n: f"{cat[:3]}.{n:x}")
    s = Shrimp(backend=MemoryBackend(scheme=scheme), scheme=scheme)
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


# -- render tests ---------------------------------------------------------------


def test_render_flat_dict() -> None:
    s = make_shrimp()
    data = {"user_id": "uuid-abc", "name": "Alice"}
    result = s.render(data, fields={"user_id": "user"})
    assert result["user_id"] == "USE_001"
    assert result["name"] == "Alice"
    # Original not mutated
    assert data["user_id"] == "uuid-abc"


def test_render_nested_list() -> None:
    s = make_shrimp()
    data = {
        "user_id": "uuid-u1",
        "orders": [{"id": "uuid-o1", "total": 50}, {"id": "uuid-o2", "total": 30}],
    }
    result = s.render(data, fields={"user_id": "user", "orders.[].id": "order"})
    assert result["user_id"] == "USE_001"
    assert result["orders"][0]["id"] == "ORD_001"
    assert result["orders"][1]["id"] == "ORD_002"
    assert result["orders"][0]["total"] == 50


def test_render_missing_field_is_noop() -> None:
    s = make_shrimp()
    data = {"name": "Alice"}
    result = s.render(data, fields={"user_id": "user"})
    assert result == {"name": "Alice"}


def test_render_stable_ids() -> None:
    s = make_shrimp()
    data = {"user_id": "uuid-1"}
    r1 = s.render(data, fields={"user_id": "user"})
    r2 = s.render(data, fields={"user_id": "user"})
    assert r1["user_id"] == r2["user_id"]


# -- resolve tests --------------------------------------------------------------


def test_resolve_known_ids() -> None:
    s = make_shrimp()
    s.encode("user", "real-uuid-1")
    s.encode("order", "real-uuid-2")
    result = s.resolve("Please check USE_001 and ORD_001.")
    assert "real-uuid-1" in result.resolved
    assert "real-uuid-2" in result.resolved
    assert result.stats["resolved"] == 2
    assert result.stats["hallucinated"] == 0
    assert result.unknown_ids == []


def test_resolve_hallucinated_ids() -> None:
    s = make_shrimp()
    result = s.resolve("User USE_999 does not exist.")
    assert "USE_999" in result.resolved  # left as-is
    assert result.stats["hallucinated"] == 1
    assert "USE_999" in result.unknown_ids


def test_resolve_mixed() -> None:
    s = make_shrimp()
    s.encode("user", "real-1")
    result = s.resolve("See USE_001 and USE_999.")
    assert "real-1" in result.resolved
    assert "USE_999" in result.resolved
    assert result.stats["resolved"] == 1
    assert result.stats["hallucinated"] == 1
    assert result.stats["rate"] == 0.5


def test_resolve_empty_text() -> None:
    s = make_shrimp()
    result = s.resolve("")
    assert result.resolved == ""
    assert result.stats["resolved"] == 0
    assert result.stats["rate"] == 0.0


def test_render_via_scoped_shrimp() -> None:
    s = make_shrimp()
    with s.scope("sess") as scoped:
        result = scoped.render({"uid": "uuid-1"}, fields={"uid": "user"})
    assert result["uid"] == "USE_001"


def test_resolve_via_scoped_shrimp() -> None:
    s = make_shrimp()
    with s.scope("sess") as scoped:
        scoped.encode("user", "real-1")
        result = scoped.resolve("Check USE_001.")
    assert "real-1" in result.resolved
