# Hugging Face Adapter for AlgoVoi

Payment-gate any Hugging Face `InferenceClient` call, `transformers` pipeline, or `smolagents` agent tool using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the other AlgoVoi AI framework adapters, plus `transformers` pipeline gating and `smolagents` Tool integration.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiHuggingFace.check() — no payment proof
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
AlgoVoiHuggingFace.check() — proof verified
        |
        v
gate.complete(messages)           → InferenceClient.chat_completion()
gate.inference_pipeline(pipe, …)  → transformers pipeline call
        |
        v
HTTP 200 — response returned
```

### smolagents tool mode (no HTTP gateway)

```
Agent reasoning loop selects AlgoVoiPaymentTool
        |
        v
tool.forward(query="...", payment_proof="...")
  → challenge JSON if proof absent/invalid
  → resource_fn(query) if payment verified
```

---

## Files

| File | Description |
|------|-------------|
| `huggingface_algovoi.py` | Adapter — `AlgoVoiHuggingFace`, `AlgoVoiPaymentTool`, `HuggingFaceResult` |
| `test_huggingface_algovoi.py` | Unit tests (all mocked, no live calls) — 83/83 |
| `example.py` | Flask + FastAPI + pipeline + smolagents deployment examples |
| `smoke_test_huggingface.py` | Two-phase smoke test (challenge render + real on-chain verification) |
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
from huggingface_algovoi import AlgoVoiHuggingFace

gate = AlgoVoiHuggingFace(
    hf_token          = "hf_...",                  # Hugging Face access token
    algovoi_key       = "algv_...",
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,                     # 0.01 USDC per call
    model             = "meta-llama/Meta-Llama-3-8B-Instruct",
)
```

### Flask — gate InferenceClient.chat_completion()

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

### transformers pipeline

```python
from transformers import pipeline

pipe = pipeline("text-generation", model="HuggingFaceH4/zephyr-7b-beta", token="hf_...")

@app.route("/ai/generate", methods=["POST"])
def generate():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    answer = gate.inference_pipeline(pipe, body.get("messages", []))
    return jsonify({"content": answer})
```

`inference_pipeline()` handles both output shapes:
- **Chat template mode** — `[{"generated_text": [{"role": "assistant", "content": "..."}]}]`
- **Plain string mode** — `[{"generated_text": "..."}]`

### smolagents tool — drop into any agent

```python
from smolagents import ToolCallingAgent, InferenceClientModel

def premium_knowledge_base(query: str) -> str:
    return f"Premium answer for: {query}"

tool = gate.as_tool(
    resource_fn      = premium_knowledge_base,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base.",
)

model  = InferenceClientModel(model_id="meta-llama/Meta-Llama-3-8B-Instruct")
agent  = ToolCallingAgent(tools=[tool], model=model)
answer = agent.run("Use premium_kb to answer: What is AlgoVoi?")
```

The agent passes:

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Question or task for the protected resource |
| `payment_proof` | string | Base64-encoded payment proof (empty → challenge returned) |

`forward(query, payment_proof)` returns challenge JSON when proof is absent/invalid, or `str(resource_fn(query))` when verified.

### Bring your own endpoint

```python
gate = AlgoVoiHuggingFace(
    algovoi_key       = "algv_...",
    tenant_id         = "...",
    payout_address    = "...",
    hf_token          = "hf_...",
    base_url          = "https://your-endpoint.endpoints.huggingface.cloud",
    model             = "meta-llama/Meta-Llama-3-8B-Instruct",
    protocol          = "ap2",
    network           = "voi-mainnet",
    amount_microunits = 5_000,
)
```

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `hf_token` | str | `None` | Hugging Face access token (`hf_...`) — used by `complete()` via `InferenceClient` |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"meta-llama/Meta-Llama-3-8B-Instruct"` | HF model ID passed to `InferenceClient` |
| `base_url` | str | `None` | Custom HF Inference Endpoint URL |
| `resource_id` | str | `"ai-inference"` | Resource identifier used in MPP challenges |

---

## Method reference

| Method | Description |
|--------|-------------|
| `check(headers[, body])` | Verify payment proof — returns `HuggingFaceResult` |
| `complete(messages)` | Call `InferenceClient.chat_completion()` after gate passes |
| `inference_pipeline(pipe, inputs)` | Run any `transformers.pipeline()` call after gate passes |
| `as_tool(resource_fn, ...)` | Return `AlgoVoiPaymentTool` for smolagents agent integration |
| `flask_guard()` | Convenience Flask handler — check + complete in one call |

---

## Dependencies

```
huggingface-hub>=0.20.0    # pip install huggingface-hub
transformers               # pip install transformers  (for inference_pipeline)
smolagents                 # pip install smolagents    (for as_tool / agent integration)
flask                      # pip install flask         (for flask_guard)
```

x402 gate reused from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
