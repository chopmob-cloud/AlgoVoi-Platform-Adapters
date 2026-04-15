# xAI (Grok) Adapter for AlgoVoi

Payment-gate the xAI Grok API (via the official `xai-sdk`) using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the OpenAI / Claude / Gemini / Bedrock / Cohere adapters.**

Full integration guide: [ai-adapters/xai/](.)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiXai.check() -- no payment proof
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
AlgoVoiXai.check() -- proof verified
        |
        v
AlgoVoiXai.complete() calls xai_sdk.Client.chat.create() + chat.sample()
        |
        v
HTTP 200 -- model response returned
```

---

## Files

| File | Description |
|------|-------------|
| `xai_algovoi.py` | Adapter — `AlgoVoiXai`, `XaiAiResult`, gate factory |
| `test_xai_algovoi.py` | Unit tests (all mocked, no live calls) |
| `example.py` | Runnable Flask + FastAPI deployment server |
| `smoke_test_xai.py` | Two-phase smoke (challenge render + real on-chain pay → Grok reply) |
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
from xai_algovoi import AlgoVoiXai

gate = AlgoVoiXai(
    xai_key           = "xai-...",                  # xAI API key
    algovoi_key       = "algv_...",                 # AlgoVoi API key
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                      # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",         # see table above
    amount_microunits = 10000,                      # 0.01 USDC per call
    model             = "grok-4",                   # default
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

---

## Message format

Accepts OpenAI-format message lists. `xai-sdk` supports the `system` role natively via `xai_sdk.chat.system()` — no extraction or remapping needed:

```python
messages = [
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user",      "content": "What can you do?"},
]

reply = gate.complete(messages)
```

Internally, each message is converted to `user()`, `system()`, or `assistant()` helpers from `xai_sdk.chat`, appended to a Chat object from `client.chat.create(model=...)`, then `chat.sample()` returns the `Response`.

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
| `xai_key` | str | required | xAI API key (starts with `xai-`) |
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"grok-4"` | Default xAI model ID |
| `resource_id` | str | `"ai-chat"` | Resource identifier used in MPP challenges |

## Supported models

Any model exposed by xAI's Grok API:

| Model ID | Description |
|----------|-------------|
| `grok-4` | Latest, most capable — **default** |
| `grok-3` | Strong general-purpose |
| `grok-3-mini` | Fast + cheap |
| `grok-2-1212` | Previous generation |
| `grok-2-vision-1212` | Vision-capable variant |

Pass `model=` to the constructor to set a default, or to `complete(messages, model=...)` to override per-call.

---

## Dependencies

```
xai-sdk>=1.0.0    # pip install xai-sdk
```

x402 gate is reused inline from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
