# Semantic Kernel Adapter for AlgoVoi

Payment-gate any Semantic Kernel chat completion, `KernelFunction`, or plugin using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the other AlgoVoi AI framework adapters, plus `kernel.invoke()` gating and `@kernel_function`-decorated plugin integration.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiSemanticKernel.check() — no payment proof
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
AlgoVoiSemanticKernel.check() — proof verified
        |
        v
gate.complete(messages)               → ChatCompletionClientBase.get_chat_message_content()
gate.invoke_function(kernel, fn, ...) → kernel.invoke(fn, ...)
        |
        v
HTTP 200 — response returned
```

### Plugin mode (no HTTP gateway)

```
LLM selects AlgoVoiPaymentPlugin.gate() via function calling
        |
        v
plugin.gate(query="...", payment_proof="...")
  → challenge JSON if proof absent/invalid
  → resource_fn(query) if payment verified
```

---

## Files

| File | Description |
|------|-------------|
| `semantic_kernel_algovoi.py` | Adapter — `AlgoVoiSemanticKernel`, `AlgoVoiPaymentPlugin`, `SemanticKernelResult` |
| `test_semantic_kernel_algovoi.py` | Unit tests (all mocked, no live calls) — 76/76 |
| `example.py` | Flask + FastAPI + KernelFunction + plugin deployment examples |
| `smoke_test_semantic_kernel.py` | Two-phase smoke test (challenge render + real on-chain verification) |
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
from semantic_kernel_algovoi import AlgoVoiSemanticKernel

gate = AlgoVoiSemanticKernel(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,                     # 0.01 USDC per call
    model             = "gpt-4o",
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
    return JSONResponse({"content": gate.complete(body["messages"])})
```

### Gate any `KernelFunction`

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

kernel = Kernel()
kernel.add_service(OpenAIChatCompletion(
    service_id  = "chat",
    ai_model_id = "gpt-4o",
    api_key     = "sk-...",
))

summarise_fn = kernel.add_function(
    plugin_name   = "utils",
    function_name = "summarise",
    prompt        = "Summarise in one sentence: {{$input}}",
)

result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.invoke_function(kernel, summarise_fn, input=body["text"])
```

`invoke_function()` wraps `kernel.invoke()` with `asyncio.run()` for synchronous use. Pass `**kwargs` directly — they are forwarded to `kernel.invoke()`.

### Plugin — add to any Kernel

```python
def premium_knowledge_base(query: str) -> str:
    return f"Premium answer for: {query}"

plugin = gate.as_plugin(
    resource_fn      = premium_knowledge_base,
    plugin_name      = "premium_kb",
    gate_description = "Query the payment-gated knowledge base.",
)

kernel.add_plugin(plugin, plugin_name="premium_kb")
```

The plugin exposes a single `@kernel_function` named `gate`:

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Question or task for the protected resource |
| `payment_proof` | str | Base64-encoded payment proof (empty → challenge returned) |

Returns challenge JSON if proof absent/invalid; calls `resource_fn(query)` and returns the result if verified. The LLM can select the function via auto-invocation when function calling is enabled.

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `openai_key` | str | `None` | OpenAI API key — used by `_ensure_kernel()` and `complete()` |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits |
| `model` | str | `"gpt-4o"` | OpenAI model ID for `OpenAIChatCompletion` service |
| `base_url` | str | `None` | Override API base URL (for Azure, compatible providers) |
| `resource_id` | str | `"ai-function"` | Resource identifier used in MPP challenges |

---

## Method reference

| Method | Description |
|--------|-------------|
| `check(headers[, body])` | Verify payment proof — returns `SemanticKernelResult` |
| `complete(messages)` | SK chat completion — sync wrapper around `get_chat_message_content()` |
| `invoke_function(kernel, function, **kwargs)` | Gate `kernel.invoke(function, ...)` — returns `str` |
| `as_plugin(resource_fn, ...)` | Return `AlgoVoiPaymentPlugin` with `@kernel_function` gate method |
| `flask_guard()` | Convenience Flask handler — check + complete in one call |

---

## Async note

SK Python v1.x is async-native. `complete()` and `invoke_function()` use `asyncio.run()` internally to provide a synchronous API consistent with the other AlgoVoi adapters. If you are already inside an async context (e.g. FastAPI route), call `_complete_async()` or `_invoke_async()` directly with `await`.

---

## Dependencies

```
semantic-kernel>=1.0.0    # pip install semantic-kernel
flask                     # pip install flask  (for flask_guard)
```

x402 gate reused from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
