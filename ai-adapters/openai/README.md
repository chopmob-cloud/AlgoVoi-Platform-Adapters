# OpenAI Adapter for AlgoVoi

Payment-gate any OpenAI (or OpenAI-compatible) API using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — 101/101 tests passing.**

Full integration guide: [ai-adapters/openai/](.)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiOpenAI.check() -- no payment proof
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
AlgoVoiOpenAI.check() -- proof verified
        |
        v
AlgoVoiOpenAI.complete() calls AI API
        |
        v
HTTP 200 -- AI response returned
```

---

## Files

| File | Description |
|------|-------------|
| `openai_algovoi.py` | Adapter — `AlgoVoiOpenAI`, inline `_X402Gate`, gate factory |
| `test_openai.py` | 101 unit tests (all mocked, no live calls) |

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
from openai_algovoi import AlgoVoiOpenAI

gate = AlgoVoiOpenAI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "x402",              # "x402" | "mpp" | "ap2"
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
    result = gate.check(dict(request.headers), request.get_json(silent=True))
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(request.json["messages"])})
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
import json

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

## OpenAI-compatible APIs

Pass `base_url` to use any OpenAI-compatible provider — the same payment gate works unchanged across all of them:

| Provider | `base_url` | Example model |
|----------|-----------|---------------|
| OpenAI (default) | *(omit `base_url`)* | `gpt-4o` |
| Mistral AI | `https://api.mistral.ai/v1` | `mistral-large-latest` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| Together AI | `https://api.together.xyz/v1` | `meta-llama/Llama-3-70b-chat-hf` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| xAI Grok | `https://api.x.ai/v1` | `grok-2-latest` |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o` |
| Fireworks AI | `https://api.fireworks.ai/inference/v1` | `accounts/fireworks/models/llama-v3p1-70b-instruct` |
| Perplexity | `https://api.perplexity.ai` | `sonar-pro` |
| Azure OpenAI | `https://{resource}.openai.azure.com/openai/deployments/{deployment}` | `gpt-4o` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.2` |

```python
# Mistral AI
gate = AlgoVoiOpenAI(
    openai_key = "YOUR_MISTRAL_KEY",
    base_url   = "https://api.mistral.ai/v1",
    model      = "mistral-large-latest",
    ...
)

# Groq — ultra-fast inference
gate = AlgoVoiOpenAI(
    openai_key = "YOUR_GROQ_KEY",
    base_url   = "https://api.groq.com/openai/v1",
    model      = "llama-3.3-70b-versatile",
    ...
)

# DeepSeek — strong coding model
gate = AlgoVoiOpenAI(
    openai_key = "YOUR_DEEPSEEK_KEY",
    base_url   = "https://api.deepseek.com/v1",
    model      = "deepseek-chat",
    ...
)

# xAI Grok
gate = AlgoVoiOpenAI(
    openai_key = "YOUR_XAI_KEY",
    base_url   = "https://api.x.ai/v1",
    model      = "grok-2-latest",
    ...
)

# OpenRouter — routes to 200+ models with a single key
gate = AlgoVoiOpenAI(
    openai_key = "YOUR_OPENROUTER_KEY",
    base_url   = "https://openrouter.ai/api/v1",
    model      = "anthropic/claude-sonnet-4-5",
    ...
)

# Fireworks AI — fast open-source inference
gate = AlgoVoiOpenAI(
    openai_key = "YOUR_FIREWORKS_KEY",
    base_url   = "https://api.fireworks.ai/inference/v1",
    model      = "accounts/fireworks/models/llama-v3p1-70b-instruct",
    ...
)

# Perplexity — search-augmented responses
gate = AlgoVoiOpenAI(
    openai_key = "YOUR_PERPLEXITY_KEY",
    base_url   = "https://api.perplexity.ai",
    model      = "sonar-pro",
    ...
)

# Azure OpenAI
gate = AlgoVoiOpenAI(
    openai_key = "YOUR_AZURE_KEY",
    base_url   = "https://YOUR_RESOURCE.openai.azure.com/openai/deployments/YOUR_DEPLOYMENT",
    model      = "gpt-4o",
    ...
)

# Ollama — local / self-hosted models, no API key needed
gate = AlgoVoiOpenAI(
    openai_key = "ollama",          # placeholder — Ollama ignores the key
    base_url   = "http://localhost:11434/v1",
    model      = "llama3.2",
    ...
)
```

---

## AP2 + MPP protocols

The AP2 and MPP gates delegate to the sibling adapters in this repo. Both are loaded via `sys.path` injection — no install step needed as long as this repo is checked out.

```python
# MPP — Algorand mainnet
gate = AlgoVoiOpenAI(
    ...,
    protocol = "mpp",
    network  = "algorand-mainnet",
    resource_id = "ai-chat",          # shown in MPP challenge
)

# AP2 — VOI mainnet
gate = AlgoVoiOpenAI(
    ...,
    protocol = "ap2",
    network  = "voi-mainnet",
)
```

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `openai_key` | str | required | OpenAI (or compatible) API key |
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `protocol` | str | `"x402"` | Payment protocol — `"x402"`, `"mpp"`, or `"ap2"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"gpt-4o"` | Default AI model |
| `base_url` | str | `None` | Override API base URL for OpenAI-compatible providers |
| `resource_id` | str | `"ai-chat"` | Resource identifier used in MPP challenges |

---

## Dependencies

```
openai>=1.0.0      # pip install openai
```

x402 gate is inline — no extra dependency.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
