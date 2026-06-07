# Mistral Adapter for AlgoVoi

Payment-gate the Mistral API (via the official `mistralai` SDK) using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the OpenAI / Claude / Gemini / Bedrock / Cohere / xAI adapters.**

Full integration guide: [ai-adapters/mistral/](.)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiMistral.check() -- no payment proof
        |
        v
HTTP 402 + protocol-specific challenge header
  x402:  X-PAYMENT-REQUIRED (spec v1, base64 JSON)
  MPP:   WWW-Authenticate: Payment (IETF draft)
  AP2:   X-AP2-Cart-Mandate (crypto-algo extension)
        |
        v
Client pays on-chain (Algorand / VOI / Hedera / Stellar)
Client sends proof in request header
        |
        v
AlgoVoiMistral.check() -- proof verified
        |
        v
AlgoVoiMistral.complete() calls Mistral.chat.complete()
        |
        v
HTTP 200 -- model response returned
```

---

## Files

| File | Description |
|------|-------------|
| `mistral_algovoi.py` | Adapter — `AlgoVoiMistral`, `MistralAiResult`, gate factory |
| `test_mistral_algovoi.py` | Unit tests (all mocked, no live calls) |
| `example.py` | Runnable Flask + FastAPI deployment server |
| `smoke_test_mistral.py` | Two-phase smoke (challenge render + real on-chain pay → Mistral reply) |
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
from mistral_algovoi import AlgoVoiMistral

gate = AlgoVoiMistral(
    mistral_key       = "...",                        # Mistral API key
    algovoi_key       = "algv_...",                   # AlgoVoi API key
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                        # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",           # see table above
    amount_microunits = 10000,                        # 0.01 USDC per call
    model             = "mistral-large-latest",       # default
)
```

### Flask

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

Or use the convenience method:

```python
@app.route("/ai/chat", methods=["POST"])
def chat():
    return gate.flask_guard()
```

### FastAPI

```python
from fastapi import FastAPI, Request
from fastapi.responses import Response

app = FastAPI()

@app.post("/ai/chat")
async def chat(req: Request):
    body   = await req.json()
    result = gate.check(dict(req.headers), body)
    if result.requires_payment:
        status, headers, body_bytes = result.as_wsgi_response()
        return Response(body_bytes, status_code=402, headers=dict(headers))
    return {"content": gate.complete(body["messages"])}
```

### Context manager (recommended for scripts)

```python
with AlgoVoiMistral(...) as gate:
    reply = gate.complete([{"role": "user", "content": "Hi"}])
# httpx transport closed automatically on exit
```

---

## Message format

Accepts OpenAI-format message lists — Mistral accepts these dicts natively:

```python
messages = [
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user",      "content": "What can you do?"},
]

reply = gate.complete(messages)
```

Recognised roles: `system`, `user`, `assistant`. Unknown roles (`tool`, `function`, etc.) are silently skipped — silently mapping them to `user` would corrupt the conversation shape and Mistral's typed validation would reject them anyway.

---

## MPP result

On MPP success, `result.receipt` provides payment details:

```python
result = gate.check(dict(request.headers), body)
if not result.requires_payment:
    print(result.receipt.payer)   # on-chain sender address
    print(result.receipt.tx_id)   # transaction ID
    print(result.receipt.amount)  # amount in microunits
```

## AP2 result

On AP2 success, `result.mandate` provides mandate details:

```python
result = gate.check(dict(request.headers), body)
if not result.requires_payment:
    print(result.mandate.payer_address)  # payer's address
    print(result.mandate.network)        # chain used
    print(result.mandate.tx_id)          # transaction ID
```

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mistral_key` | str | required | Mistral API key |
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"mistral-large-latest"` | Default Mistral model ID |
| `resource_id` | str | `"ai-chat"` | Resource identifier used in MPP challenges |

## Supported models

Any model exposed by Mistral's API:

| Model ID | Description |
|----------|-------------|
| `mistral-large-latest` | Flagship — **default** |
| `mistral-medium-latest` | Balanced cost / quality |
| `mistral-small-latest` | Fastest / cheapest |
| `codestral-latest` | Code-specialised |
| `open-mistral-nemo` | Open-weight, 12B |
| `pixtral-large-latest` | Vision-capable |

Pass `model=` to the constructor to set a default, or to `complete(messages, model=...)` to override per-call.

---

## Dependencies

```
mistralai>=2.0.0    # pip install mistralai
```

x402 gate is reused inline from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
