# LangChain Adapter for AlgoVoi

Payment-gate any LangChain LLM, chain, or agent endpoint using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the OpenAI / Claude / Gemini / Bedrock / Cohere / xAI / Mistral adapters, plus LangChain-native chain invocation and agent tool support.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiLangChain.check() — no payment proof
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
AlgoVoiLangChain.check() — proof verified
        |
        v
gate.complete(messages)         → ChatOpenAI via LangChain
gate.invoke_chain(chain, input) → any LangChain Runnable
        |
        v
HTTP 200 — response returned
```

---

## Files

| File | Description |
|------|-------------|
| `langchain_algovoi.py` | Adapter — `AlgoVoiLangChain`, `AlgoVoiPaymentTool`, `LangChainResult` |
| `test_langchain_algovoi.py` | Unit tests (all mocked, no live calls) |
| `example.py` | Flask + FastAPI + agent deployment examples |
| `smoke_test_langchain.py` | Two-phase smoke test (challenge render + real on-chain verification) |
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
from langchain_algovoi import AlgoVoiLangChain

gate = AlgoVoiLangChain(
    openai_key        = "sk-...",                  # OpenAI key for ChatOpenAI
    algovoi_key       = "algv_...",                # AlgoVoi API key
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",        # see table above
    amount_microunits = 10000,                     # 0.01 USDC per call
)
```

### Flask

```python
from flask import Flask, request, jsonify, Response
app = Flask(__name__)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})
```

Or use the convenience wrapper:

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

### Custom chain (LCEL)

Gate any LangChain Runnable — RAG pipelines, sequential chains, etc.:

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

chain = (
    ChatPromptTemplate.from_template("Answer: {question}")
    | ChatOpenAI(model="gpt-4o")
    | StrOutputParser()
)

result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.invoke_chain(chain, {"question": body["question"]})
```

### Bring your own LangChain model

Pass any pre-built ChatModel to skip the ChatOpenAI constructor:

```python
from langchain_anthropic import ChatAnthropic

gate = AlgoVoiLangChain(
    algovoi_key    = "algv_...",
    tenant_id      = "...",
    payout_address = "...",
    llm            = ChatAnthropic(model="claude-opus-4-5"),
)
```

### Agent tool

Drop `AlgoVoiPaymentTool` into any LangChain ReAct agent:

```python
def my_protected_fn(query: str) -> str:
    return f"Premium answer to: {query}"

tool = gate.as_tool(
    resource_fn      = my_protected_fn,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base.",
)

from langchain.agents import create_react_agent, AgentExecutor
agent    = create_react_agent(llm, [tool], prompt)
executor = AgentExecutor(agent=agent, tools=[tool])
```

The tool accepts JSON input:
```json
{"query": "What is the answer?", "payment_proof": "<base64 proof>"}
```

Returns challenge JSON if proof is missing/invalid, resource result if verified.

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

Recognised roles: `system`, `user`, `assistant`. Unknown roles are silently skipped.

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
| `llm` | Any | `None` | Pre-built LangChain ChatModel (takes precedence over `openai_key`) |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"gpt-4o"` | ChatOpenAI model ID (ignored when `llm=` is passed) |
| `base_url` | str | `None` | Override OpenAI API base URL (for compatible providers) |
| `resource_id` | str | `"ai-chat"` | Resource identifier used in MPP challenges |

---

## OpenAI-compatible providers

Pass `base_url=` to use any OpenAI-compatible API with `ChatOpenAI`:

| Provider | base_url |
|----------|----------|
| OpenAI | `https://api.openai.com/v1` (default) |
| Together AI | `https://api.together.xyz/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| Perplexity | `https://api.perplexity.ai` |
| Mistral | `https://api.mistral.ai/v1` |

Or pass any LangChain chat model directly via `llm=` (Anthropic, Google, Bedrock, etc.).

---

## Dependencies

```
langchain-core>=0.1.0     # pip install langchain-core
langchain-openai>=0.1.0   # pip install langchain-openai  (for complete())
pydantic>=2.0             # pip install pydantic          (for as_tool())
```

x402 gate reused inline from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
