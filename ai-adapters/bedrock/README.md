# Amazon Bedrock Adapter for AlgoVoi

Payment-gate the Amazon Bedrock Converse API using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — 57/57 tests passing.**

Full integration guide: [ai-adapters/bedrock/](.)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiBedrock.check() -- no payment proof
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
AlgoVoiBedrock.check() -- proof verified
        |
        v
AlgoVoiBedrock.complete() calls Bedrock Converse API
        |
        v
HTTP 200 -- model response returned
```

---

## Files

| File | Description |
|------|-------------|
| `bedrock_algovoi.py` | Adapter — `AlgoVoiBedrock`, `BedrockAiResult`, gate factory |
| `test_bedrock_algovoi.py` | 57 unit tests (all mocked, no live calls) |
| `example.py` | Runnable Flask + FastAPI deployment server |

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
from bedrock_algovoi import AlgoVoiBedrock

gate = AlgoVoiBedrock(
    aws_access_key_id     = "AKIA...",       # or set AWS_ACCESS_KEY_ID env var
    aws_secret_access_key = "wJal...",       # or set AWS_SECRET_ACCESS_KEY env var
    aws_region            = "us-east-1",
    algovoi_key           = "algv_...",
    tenant_id             = "<your-tenant-uuid>",
    payout_address        = "<your-algorand-address>",
    protocol              = "mpp",               # "mpp" | "ap2" | "x402"
    network               = "algorand-mainnet",  # see table above
    amount_microunits     = 10000,               # 0.01 USDC per call
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

Accepts OpenAI-format message lists — the `system` role is extracted automatically into Bedrock's separate `system` parameter:

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
| `aws_access_key_id` | str | `None` | AWS access key (or `AWS_ACCESS_KEY_ID` env var) |
| `aws_secret_access_key` | str | `None` | AWS secret key (or `AWS_SECRET_ACCESS_KEY` env var) |
| `aws_region` | str | `"us-east-1"` | AWS region where Bedrock is enabled |
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"amazon.nova-pro-v1:0"` | Default Bedrock model ID |
| `max_tokens` | int | `1024` | Max tokens in response |
| `resource_id` | str | `"ai-chat"` | Resource identifier used in MPP challenges |

## Supported models

Any model available in your AWS account via the Bedrock Converse API is supported. Common options:

| Model ID | Description |
|----------|-------------|
| `amazon.nova-pro-v1:0` | Amazon Nova Pro — default |
| `amazon.nova-lite-v1:0` | Amazon Nova Lite — fast |
| `anthropic.claude-3-5-sonnet-20241022-v2:0` | Claude 3.5 Sonnet via Bedrock |
| `meta.llama3-70b-instruct-v1:0` | Meta Llama 3 70B |
| `amazon.titan-text-premier-v1:0` | Amazon Titan Premier |

Model availability depends on your AWS region and Bedrock access grants.

---

## AWS credentials

Pass credentials directly to the constructor, or set the standard AWS environment variables:

```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="wJal..."
export AWS_DEFAULT_REGION="us-east-1"
```

When environment variables are set, omit `aws_access_key_id` and `aws_secret_access_key` from the constructor — boto3 picks them up automatically.

---

## Dependencies

```
boto3>=1.26.0    # pip install boto3
```

x402 gate is inline — no extra dependency.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
