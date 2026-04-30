# 🦐 Shrimp

**Shrimp your UUIDs. Tiny IDs for big language models.**

Shrimp turns long, opaque IDs (UUIDs, hashes, DB keys) into short, category-prefixed aliases that LLMs can actually read, reason about, and reference back without hallucinating.

```
f47ac10b-58cc-4372-a567-0e02b2c3d479   →   USR_001
8a3f9d2e-...                            →   ORD_042
```

## Why

Passing UUIDs to an LLM is wasteful and risky:

- **Tokens.** A UUID is ~13 tokens. Multiply by every row in every search result.
- **Hallucination.** LLMs flip characters in long opaque strings. One wrong hex char and you're pointing at nothing — or worse, the wrong row.
- **Debuggability.** `USR_003 messaged USR_007` is readable. The UUID version is not.

Shrimp gives you a stable, scoped alias on the way in, and resolves it back on the way out.

## Install

```bash
pip install shrimp
```

## Quickstart

```python
from shrimp import Shrimp

shrimp = Shrimp(redis_url="redis://localhost:6379")

# Encode
short = shrimp.encode("user", "f47ac10b-58cc-4372-a567-0e02b2c3d479")
# -> "USR_001"

# Decode
category, real_id = shrimp.decode("USR_001")
# -> ("user", "f47ac10b-58cc-4372-a567-0e02b2c3d479")
```

No Redis? Use the in-memory backend:

```python
from shrimp import Shrimp
from shrimp.backends import MemoryBackend

shrimp = Shrimp(backend=MemoryBackend())
```

## Render structured data

Walk a nested object and swap registered fields with short IDs before sending to the model:

```python
data = {
    "user_id": "f47ac10b-...",
    "orders": [{"id": "8a3f...", "total": 50}],
}

rendered = shrimp.render(data, fields={
    "user_id": "user",
    "orders.[].id": "order",
})
# {"user_id": "USR_001", "orders": [{"id": "ORD_001", "total": 50}]}
```

## Resolve LLM output

Catch hallucinated IDs and substitute real ones back:

```python
result = shrimp.resolve(llm_response_text)

print(result.resolved)       # text with real UUIDs restored
print(result.unknown_ids)    # IDs the model made up
print(result.stats)          # {"resolved": 4, "hallucinated": 1, "rate": 0.2}
```

## Customize the scheme

```python
from shrimp import Shrimp, Scheme

scheme = Scheme(
    prefix_map={"user": "U", "order": "O"},
    separator="-",
    counter_format="{:04d}",   # U-0001, U-0002
)

shrimp = Shrimp(redis_url="...", scheme=scheme)
```

Or take full control:

```python
scheme = Scheme(aliaser=lambda category, n: f"{category[:3]}.{n:x}")
# user.1, user.2, ..., ord.a
```

## Scopes

Mappings are scoped so different sessions or requests don't leak into each other:

```python
with shrimp.scope("session_123") as s:
    s.encode("user", uuid)

# Auto-expire after 1 hour
shrimp.create_scope("session_123", ttl_seconds=3600)
```

## What Shrimp is not

- Not a vector store, not a memory system, not a prompt framework.
- Not a security boundary. Short IDs are scoped tokens, not auth.
- Not a general-purpose ID generator (use [Sqids](https://sqids.org) or ULID for that).

## Status

Pre-release. APIs may shift before v1.0. Issues and PRs welcome.

## License

MIT