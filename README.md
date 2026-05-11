# 🦐 Shrimp — Tiny IDs for LLMs

[![PyPI version](https://img.shields.io/pypi/v/shrimp-llm.svg)](https://pypi.org/project/shrimp-llm/)
[![Downloads](https://img.shields.io/pypi/dm/shrimp-llm.svg)](https://pypi.org/project/shrimp-llm/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/shrimp-llm.svg)](https://pypi.org/project/shrimp-llm/)
[![CI](https://github.com/fsabuhi/shrimp/actions/workflows/ci.yml/badge.svg)](https://github.com/fsabuhi/shrimp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Stop wasting tokens on UUIDs.** Shrimp is a Python library that shortens UUIDs, hashes, and database keys into tiny, readable, category-prefixed aliases optimized for LLM context windows — reducing token cost, preventing hallucination, and making agent output human-readable.

> A single UUID burns ~13 tokens. Shrimp aliases use 1–2. Across a RAG pipeline, tool-calling agent, or multi-turn chat, the savings compound into faster responses, lower cost, and fewer hallucinated IDs.

```
f47ac10b-58cc-4372-a567-0e02b2c3d479   →   USR_001
8a3f9d2e-7b14-4c5a-9d8e-1f2a3b4c5d6e   →   ORD_042
```

---

## Why Shrimp? The UUID Problem in LLM Applications

Every time you pass a UUID into a prompt — whether you're building with OpenAI, Anthropic Claude, Google Gemini, or open-source models — you pay three costs:

| | Raw UUID | Shrimp alias |
|---|---|---|
| **Token cost** | ~13 tokens per ID | 1–2 tokens |
| **Hallucination risk** | LLMs flip hex characters → silent wrong-row bugs | Short IDs are verifiable & scoped |
| **Readability** | `f47ac10b…` told `8a3f9d2e…` | `USR_003` messaged `USR_007` |

Multiply that by every row in every tool call, every RAG retrieval result, every agent step. It adds up fast — more tokens mean higher latency, higher cost, and more room for the model to hallucinate an ID.

**Shrimp gives you a stable, scoped alias on the way in — and resolves it back on the way out.**

## Features

- **Encode / Decode** — bidirectional mapping between real IDs and short aliases
- **Render** — deep-walk nested dicts/lists and swap ID fields before sending to the model
- **Resolve** — scan LLM output, restore real IDs, and flag hallucinated ones
- **Scopes** — isolate mappings per session, request, or user with optional TTL
- **Customizable schemes** — control prefixes, separators, counters, or bring your own aliaser
- **Pluggable backends** — in-memory (zero deps) or Redis for production
- **Zero required dependencies** — core library has no third-party requirements
- **Type-safe** — fully typed with `mypy --strict`

## Install

```bash
pip install shrimp-llm
```

With Redis support:

```bash
pip install shrimp-llm[redis]
```

## Quickstart

```python
from shrimp import Shrimp

shrimp = Shrimp()  # in-memory, zero config

# Encode: real ID → short alias
short = shrimp.encode("user", "f47ac10b-58cc-4372-a567-0e02b2c3d479")
# → "USR_001"

# Decode: short alias → real ID
category, real_id = shrimp.decode("USR_001")
# → ("user", "f47ac10b-58cc-4372-a567-0e02b2c3d479")
```

With Redis:

```python
shrimp = Shrimp(redis_url="redis://localhost:6379")
```

## Usage

### Render structured data

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

### Resolve LLM output

Catch hallucinated IDs and substitute real ones back:

```python
result = shrimp.resolve(llm_response_text)

print(result.resolved)       # text with real UUIDs restored
print(result.unknown_ids)    # IDs the model made up
print(result.stats)          # {"resolved": 4, "hallucinated": 1, "rate": 0.2}
```

### Scopes

Isolate mappings per session or request so they don't leak into each other:

```python
with shrimp.scope("session_123") as s:
    s.encode("user", uuid)

# Auto-expire after 1 hour (Redis backend)
shrimp.create_scope("session_123", ttl_seconds=3600)
```

### Custom schemes

```python
from shrimp import Shrimp, Scheme

scheme = Scheme(
    prefix_map={"user": "U", "order": "O"},
    separator="-",
    counter_format="{:04d}",   # U-0001, U-0002
)

shrimp = Shrimp(redis_url="...", scheme=scheme)
```

Or take full control with a custom aliaser:

```python
scheme = Scheme(aliaser=lambda category, n: f"{category[:3]}.{n:x}")
# user.1, user.2, ..., ord.a
```

## When to Use Shrimp

- **RAG pipelines** — replace document/chunk IDs before stuffing into the context window
- **AI agent tool calls** — give the LLM readable handles for database rows, API resources, CRM records
- **OpenAI function calling / tool use** — short IDs in function arguments reduce token overhead and parsing errors
- **Chat with structured data** — render tables/JSON with short IDs, resolve them in the LLM response
- **Multi-turn conversations** — scope aliases per conversation to keep context clean across turns
- **LLM evaluation & debugging** — instantly see which entities the model is referencing
- **Cost optimization** — cut prompt token counts when working with ID-heavy payloads

## Works With

Shrimp is framework-agnostic. Use it with any LLM provider or orchestration library:

- **LLM providers** — OpenAI, Anthropic Claude, Google Gemini, Mistral, Cohere, local models via Ollama/vLLM
- **Orchestration** — LangChain, LlamaIndex, Haystack, Semantic Kernel, or plain API calls
- **Backends** — in-memory (zero deps, great for scripts & notebooks) or Redis (production, shared state, TTL)

## What Shrimp Is Not

- Not a vector store, not a memory system, not a prompt framework.
- Not a security boundary — short IDs are scoped tokens, not auth.
- Not a general-purpose ID generator (use [Sqids](https://sqids.org) or ULID for that).

## Contributing

Contributions are welcome! Here's how to get started:

```bash
git clone https://github.com/fsabuhi/shrimp.git
cd shrimp
pip install -e ".[dev]"
pytest
```

Please open an issue before submitting large PRs.

## License

MIT

---

**Keywords:** shorten UUIDs for LLMs, reduce LLM token count, LLM ID aliasing, prevent UUID hallucination, context window optimization, token-efficient IDs, AI agent tool call optimization, short ID mapping Python, UUID to alias converter, LLM prompt optimization