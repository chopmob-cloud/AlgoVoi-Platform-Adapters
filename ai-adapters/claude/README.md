# Claude Adapter for AlgoVoi

Payment-gate the Anthropic Claude API using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — 76/76 tests passing. Smoke-tested on all 4 chains 14 Apr 2026.**

Full integration guide: [ai-adapters/claude/](.)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiClaude.check() -- no payment proof
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
AlgoVoiClaude.check() -- proof verified
        |
        v
AlgoVoiClaude.complete() calls Anthropic API
        |
        v
HTTP 200 -- Claude response returned
```

---

## Files

| File | Description |
|------|-------------|
| `claude_algovoi.py` | Adapter — `AlgoVoiClaude`, `ClaudeAiResult`, gate factory |
| `test_claude_algovoi.py` | 76 unit tests (all mocked, no live calls) |
| `smoke_test_claude.py` | MPP live smoke test — all 4 chains |
| `smoke_test_claude_ap2.py` | AP2 live smoke test — Algorand mainnet |

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
from claude_algovoi import AlgoVoiClaude

gate = AlgoVoiClaude(
    anthropic_key     = "sk-ant-...",
    algovoi_key       = "algv_...",
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",               # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",  # see table above
    amount_microunits = 10000,               # 0.01 USDC per call
)
```

### Flask

```python
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
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
    body = await req.json()
    result = gate.check(dict(req.headers), body)
    if result.requires_payment:
        status, headers, body_bytes = result.as_wsgi_response()
        return Response(body_bytes, status_code=402, headers=dict(headers))
    return {"content": gate.complete(body["messages"])}
```

---

## Message format

Accepts OpenAI-format message lists — the `system` role is extracted automatically into Anthropic's separate `system` parameter:

```python
messages = [
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user",      "content": "What can you do?"},
]

reply = gate.complete(messages)
```

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
| `anthropic_key` | str | required | Anthropic API key (`sk-ant-...`) |
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"claude-sonnet-4-5"` | Default Claude model |
| `max_tokens` | int | `1024` | Max tokens in response |
| `resource_id` | str | `"ai-chat"` | Resource identifier used in MPP challenges |

## Supported models

| Model ID | Description |
|----------|-------------|
| `claude-opus-4-5` | Most capable |
| `claude-sonnet-4-5` | Balanced — default |
| `claude-haiku-4-5` | Fastest |

---

## Dependencies

```
anthropic>=0.20.0    # pip install anthropic
```

x402 gate is inline — no extra dependency.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
