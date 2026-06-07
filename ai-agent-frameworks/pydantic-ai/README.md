# Pydantic AI Adapter for AlgoVoi

Payment-gate any Pydantic AI agent or model call using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the other AlgoVoi AI framework adapters, plus `run_agent()` gating for any Pydantic AI `Agent` with dependency injection support.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiPydanticAI.check() — no payment proof
        |
        v
HTTP 402 + protocol challenge header
  x402:  X-PAYMENT-REQUIRED (spec v1, base64 JSON)
  MPP:   WWW-Authenticate: Payment (IETF draft)
  AP2:   X-AP2-Cart-Mandate (crypto-algo extension)
        |
        v
Client pays on-chain (Algorand / VOI / Hedera / Stellar)
Client re-sends with proof in header
        |
        v
AlgoVoiPydanticAI.check() — proof verified
        |
        v
gate.complete(messages)           → Agent.run(prompt)
gate.run_agent(agent, prompt, ...) → agent.run(prompt, deps=deps)
        |
        v
HTTP 200 — response returned
```

### Tool mode (no HTTP gateway)

```
LLM selects AlgoVoiPaymentTool via function calling
        |
        v
tool(query="...", payment_proof="...")
  → challenge JSON if proof absent/invalid
  → resource_fn(query) if payment verified
```

---

## Files

| File | Description |
|------|-------------|
| `pydanticai_algovoi.py` | Adapter — `AlgoVoiPydanticAI`, `AlgoVoiPaymentTool`, `PydanticAIResult` |
| `test_pydanticai_algovoi.py` | Unit tests (all mocked, no live calls) — 77/77 |
| `example.py` | Flask + FastAPI + Agent + tool + custom provider examples |
| `smoke_test_pydanticai.py` | Two-phase smoke test (challenge render + real on-chain verification) |
| `README.md` | This file |

---

## Supported chains

| Network key | Asset | Asset ID |
|-------------|-------|----------|
| `algorand-mainnet` | USDC | ASA 31566704 |
| `voi-mainnet` | aUSDC | ARC200 302190 |
| `hedera-mainnet` | USDC | HTS 0.0.456858 |
| `stellar-mainnet` | USDC | Circle |

## Supported protocols

| Key | Spec |
|-----|------|
| `x402` | x402 spec v1 — `X-PAYMENT-REQUIRED` / `X-PAYMENT` |
| `mpp` | IETF draft-ryan-httpauth-payment — `WWW-Authenticate: Payment` |
| `ap2` | AP2 v0.1 + AlgoVoi crypto-algo extension |

---

## Quick start

```python
from pydanticai_algovoi import AlgoVoiPydanticAI

gate = AlgoVoiPydanticAI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,                     # 0.01 USDC per call
    model             = "openai:gpt-4o",           # any Pydantic AI model string
)
```

### Flask — gate chat completion

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Or use the convenience one-liner:

```python
@app.route("/ai/chat", methods=["POST"])
def chat():
    return gate.flask_guard()
```

### FastAPI

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

@app.post("/ai/chat")
async def chat(req: Request):
    body   = await req.json()
    result = gate.check(dict(req.headers), body)
    if result.requires_payment:
        status, headers, body_bytes = result.as_wsgi_response()
        return Response(body_bytes, status_code=402, headers=dict(headers))
    reply = await gate._complete_async(body["messages"])   # async path
    return JSONResponse({"content": reply})
```

### Gate any pre-built Pydantic AI Agent

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from openai import AsyncOpenAI

openai_client = AsyncOpenAI(api_key="sk-...")
my_agent = Agent(
    OpenAIModel("gpt-4o", openai_client=openai_client),
    system_prompt="You are a concise assistant.",
)

result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.run_agent(my_agent, body["prompt"])
```

`run_agent()` wraps `agent.run()` with `asyncio.run()` for synchronous use. Pass `deps` and any `**kwargs` directly — they are forwarded to `agent.run()`.

### Dependency injection

```python
from pydantic_ai import Agent
from dataclasses import dataclass

@dataclass
class UserDeps:
    user_id: str
    tier: str

premium_agent = Agent("openai:gpt-4o", deps_type=UserDeps)

result = gate.check(headers, body)
if not result.requires_payment:
    deps   = UserDeps(user_id=body["user_id"], tier="premium")
    output = gate.run_agent(premium_agent, body["prompt"], deps=deps)
```

### Payment tool — add to any Agent

```python
def premium_knowledge_base(query: str) -> str:
    return f"Premium answer for: {query}"

tool = gate.as_tool(
    resource_fn      = premium_knowledge_base,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base.",
)

from pydantic_ai import Agent
from pydantic_ai.tools import Tool

agent = Agent(
    "openai:gpt-4o",
    tools=[Tool(tool, name=tool.name, description=tool.description)],
)
```

The tool accepts `query` and `payment_proof` (base64). Returns challenge JSON if proof absent/invalid; calls `resource_fn(query)` if verified.

---

## Supported model providers

Pydantic AI uses a `provider:model` string or an explicit `Model` object:

| Provider | Model string example | Notes |
|----------|---------------------|-------|
| OpenAI | `"openai:gpt-4o"` | Default — `openai_key` or `OPENAI_API_KEY` |
| Anthropic | `"anthropic:claude-opus-4-5"` | `ANTHROPIC_API_KEY` env var |
| Google Gemini | `"google-gla:gemini-2.0-flash"` | `GEMINI_API_KEY` env var |
| Groq | OpenAI-compat via `base_url` | `base_url="https://api.groq.com/openai/v1"` |
| Ollama | OpenAI-compat via `base_url` | `base_url="http://localhost:11434/v1"` |
| Any OpenAI-compatible | Set `base_url` + `openai_key` | xAI, Together AI, Perplexity, etc. |

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `openai_key` | str | `None` | OpenAI (or compatible) API key — passed to `AsyncOpenAI` |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits |
| `model` | str | `"openai:gpt-4o"` | Pydantic AI model string (`provider:model`) |
| `base_url` | str | `None` | Override API base URL (Groq, Ollama, Azure, etc.) |
| `resource_id` | str | `"ai-function"` | Resource identifier used in MPP challenges |

---

## Method reference

| Method | Description |
|--------|-------------|
| `check(headers[, body])` | Verify payment proof — returns `PydanticAIResult` |
| `complete(messages)` | Run OpenAI-format message list through an Agent — sync wrapper |
| `run_agent(agent, prompt[, deps, **kwargs])` | Gate any Pydantic AI Agent — sync wrapper around `agent.run()` |
| `as_tool(resource_fn, ...)` | Return `AlgoVoiPaymentTool` (callable + `.name` + `.description`) |
| `flask_guard()` | Convenience Flask handler — check + complete in one call |

---

## Async note

Pydantic AI is async-native. `complete()` and `run_agent()` use `asyncio.run()` internally to provide a synchronous API consistent with the other AlgoVoi adapters. If you are already inside an async context (e.g. FastAPI route), call `_complete_async()` or `_run_async()` directly with `await`.

---

## Dependencies

```
pydantic-ai>=0.0.14    # pip install pydantic-ai
flask                   # pip install flask  (for flask_guard)
openai                  # pip install openai  (for OpenAI/compatible providers)
```

x402 gate reused from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
