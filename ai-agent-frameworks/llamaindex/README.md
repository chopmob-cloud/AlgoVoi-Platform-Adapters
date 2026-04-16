# LlamaIndex Adapter for AlgoVoi

Payment-gate any LlamaIndex LLM, query engine, chat engine, or ReAct agent tool using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the OpenAI / Claude / Gemini / Bedrock / Cohere / xAI / Mistral / LangChain adapters, plus LlamaIndex-native query engine, chat engine, and agent tool support.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiLlamaIndex.check() — no payment proof
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
AlgoVoiLlamaIndex.check() — proof verified
        |
        v
gate.complete(messages)                → OpenAI LLM via LlamaIndex
gate.query_engine_query(engine, query) → any LlamaIndex QueryEngine
gate.chat_engine_chat(engine, message) → any LlamaIndex ChatEngine
        |
        v
HTTP 200 — response returned
```

---

## Files

| File | Description |
|------|-------------|
| `llamaindex_algovoi.py` | Adapter — `AlgoVoiLlamaIndex`, `AlgoVoiPaymentTool`, `LlamaIndexResult` |
| `test_llamaindex_algovoi.py` | Unit tests (all mocked, no live calls) — 80/80 |
| `example.py` | Flask + FastAPI + ReAct agent deployment examples |
| `smoke_test_llamaindex.py` | Two-phase smoke test (challenge render + real on-chain verification) |
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
from llamaindex_algovoi import AlgoVoiLlamaIndex

gate = AlgoVoiLlamaIndex(
    openai_key        = "sk-...",                  # OpenAI key for LlamaIndex OpenAI LLM
    algovoi_key       = "algv_...",                # AlgoVoi API key
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",        # see table above
    amount_microunits = 10000,                     # 0.01 USDC per call
)
```

### Flask — LLM completion

```python
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route("/ai/complete", methods=["POST"])
def complete():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Or use the convenience wrapper:

```python
@app.route("/ai/complete", methods=["POST"])
def complete():
    return gate.flask_guard()
```

### FastAPI

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

@app.post("/ai/complete")
async def complete(req: Request):
    body   = await req.json()
    result = gate.check(dict(req.headers), body)
    if result.requires_payment:
        status, headers, body_bytes = result.as_wsgi_response()
        return Response(body_bytes, status_code=402, headers=dict(headers))
    return JSONResponse({"content": gate.complete(body["messages"])})
```

### Gate a QueryEngine (RAG pipeline)

Payment-gate any LlamaIndex `VectorStoreIndex` or custom query engine:

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

documents    = SimpleDirectoryReader("docs/").load_data()
index        = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()

result = gate.check(headers, body)
if not result.requires_payment:
    answer = gate.query_engine_query(query_engine, body["query"])
```

### Gate a ChatEngine (multi-turn)

```python
chat_engine = index.as_chat_engine(chat_mode="best")

result = gate.check(headers, body)
if not result.requires_payment:
    reply = gate.chat_engine_chat(chat_engine, body["message"])
```

### Bring your own LlamaIndex LLM

Pass any pre-built LlamaIndex `LLM` instance directly:

```python
from llama_index.llms.anthropic import Anthropic

gate = AlgoVoiLlamaIndex(
    algovoi_key    = "algv_...",
    tenant_id      = "...",
    payout_address = "...",
    llm            = Anthropic(model="claude-opus-4-5"),
)
```

### ReAct agent tool

Drop `AlgoVoiPaymentTool` into any LlamaIndex ReAct or function-calling agent:

```python
from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI

def my_protected_fn(query: str) -> str:
    return f"Premium answer to: {query}"

tool = gate.as_tool(
    resource_fn      = my_protected_fn,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base.",
)

llm   = OpenAI(model="gpt-4o", api_key="sk-...")
agent = ReActAgent.from_tools([tool], llm=llm, verbose=True)
agent.chat("What is the settlement time?")
```

The tool accepts JSON input:
```json
{"query": "What is the answer?", "payment_proof": "<base64 proof>"}
```

Returns challenge JSON if proof is missing/invalid; `resource_fn(query)` result if verified. The `__call__` method returns a `ToolOutput` with `.content`, `.tool_name`, `.raw_input`, `.raw_output`.

---

## Message format

OpenAI-format message lists — same as all other AlgoVoi AI adapters:

```python
messages = [
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user",      "content": "What can you do?"},
]

reply = gate.complete(messages)
```

Recognised roles: `system`, `user`, `assistant`. Unknown roles (`tool`, `function`, etc.) are silently skipped. Roles are mapped to LlamaIndex `MessageRole` enum values internally.

---

## MPP / AP2 result details

```python
result = gate.check(headers, body)
if not result.requires_payment:
    # MPP
    print(result.receipt.payer)   # on-chain sender address
    print(result.receipt.tx_id)
    print(result.receipt.amount)

    # AP2
    print(result.mandate.payer_address)
    print(result.mandate.network)
    print(result.mandate.tx_id)
```

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `openai_key` | str | `None` | OpenAI key — used by `complete()` if `llm=` not passed |
| `llm` | Any | `None` | Pre-built LlamaIndex `LLM` instance (takes precedence over `openai_key`) |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"gpt-4o"` | LlamaIndex OpenAI model ID (ignored when `llm=` is passed) |
| `base_url` | str | `None` | Override OpenAI API base URL (`api_base` in LlamaIndex — for compatible providers) |
| `resource_id` | str | `"ai-query"` | Resource identifier used in MPP challenges |

---

## OpenAI-compatible providers

Pass `base_url=` to use any OpenAI-compatible API with the LlamaIndex OpenAI LLM:

| Provider | base_url |
|----------|----------|
| OpenAI | `https://api.openai.com/v1` (default) |
| Together AI | `https://api.together.xyz/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| Perplexity | `https://api.perplexity.ai` |
| Mistral | `https://api.mistral.ai/v1` |

Or pass any LlamaIndex LLM directly via `llm=` (Anthropic, Google, Bedrock, Cohere, etc.).

---

## Dependencies

```
llama-index-core>=0.10.0    # pip install llama-index-core
llama-index-llms-openai>=0.1.0  # pip install llama-index-llms-openai  (for complete())
```

Or install the meta-package which includes both:
```
pip install llama-index
```

x402 gate reused inline from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
