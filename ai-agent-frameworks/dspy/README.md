# DSPy Adapter for AlgoVoi

Payment-gate any DSPy module, program, or chain using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the other AlgoVoi AI framework adapters, plus `run_module()` for gating any DSPy Predict / ChainOfThought / ReAct / compiled program.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiDSPy.check() — no payment proof
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
AlgoVoiDSPy.check() — proof verified
        |
        v
gate.complete(messages)           → dspy.Predict(_Completion)(prompt=...)
gate.run_module(module, **kwargs)  → module(**kwargs) inside dspy.context(lm=...)
        |
        v
HTTP 200 — response returned
```

All LLM calls use `dspy.context(lm=...)` — global `dspy.configure()` state is never touched.

### Tool mode (no HTTP gateway)

```
LLM (ReAct agent) selects AlgoVoiPaymentTool
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
| `dspy_algovoi.py` | Adapter — `AlgoVoiDSPy`, `AlgoVoiPaymentTool`, `DSPyResult` |
| `test_dspy_algovoi.py` | Unit tests (all mocked, no live calls) — 78/78 |
| `example.py` | Flask + ReAct tool + ChainOfThought + WSGI middleware + provider examples |
| `smoke_test_dspy.py` | Two-phase smoke test (challenge render + real on-chain verification) |
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

```bash
pip install dspy flask
```

```python
from dspy_algovoi import AlgoVoiDSPy

gate = AlgoVoiDSPy(
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    openai_key        = "sk-...",         # or omit → OPENAI_API_KEY env var
    protocol          = "mpp",            # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10_000,           # 0.01 USDC
    model             = "openai/gpt-4o",  # DSPy provider/model string
)
```

### Flask endpoint

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/ai/chat", methods=["POST"])
def chat():
    result = gate.check(dict(request.headers), request.get_json(silent=True) or {})
    if result.requires_payment:
        return result.as_flask_response()
    content = gate.complete(request.json.get("messages", []))
    return jsonify({"content": content})
```

### One-liner Flask guard

```python
@app.route("/ai/v2/chat", methods=["POST"])
def chat():
    return gate.flask_guard()
```

### Gate any DSPy module

```python
import dspy

class QA(dspy.Signature):
    """Answer the question."""
    question: str = dspy.InputField()
    answer:   str = dspy.OutputField()

# Gate a Predict module
result = gate.run_module(dspy.Predict(QA), question="What is DSPy?")

# Gate a ChainOfThought module
result = gate.run_module(dspy.ChainOfThought(QA), question="Explain on-chain payments.")

# Gate any compiled program
my_compiled_program = ...
result = gate.run_module(my_compiled_program, question="...")
```

### ReAct agent with payment tool

```python
payment_tool = gate.as_tool(
    resource_fn=lambda q: my_premium_handler(q),
    tool_name="premium_kb",
    tool_description="Access premium knowledge base. Provide query and payment_proof.",
)

class AgentQA(dspy.Signature):
    """Answer using available tools."""
    question: str = dspy.InputField()
    answer:   str = dspy.OutputField()

react = dspy.ReAct(AgentQA, tools=[payment_tool])

lm = gate._ensure_lm()
with dspy.context(lm=lm):
    result = react(question="What is the premium answer to X?")
```

---

## Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | `str` | required | `algv_...` API key |
| `tenant_id` | `str` | required | AlgoVoi tenant UUID |
| `payout_address` | `str` | required | On-chain payout address |
| `openai_key` | `str` | `None` | OpenAI API key (or env var) |
| `protocol` | `str` | `"mpp"` | Payment protocol |
| `network` | `str` | `"algorand-mainnet"` | Blockchain network |
| `amount_microunits` | `int` | `10000` | Amount in micro-USDC (10000 = $0.01) |
| `model` | `str` | `"openai/gpt-4o"` | DSPy `provider/model` string |
| `base_url` | `str` | `None` | Custom API base URL (`api_base` in DSPy) |
| `resource_id` | `str` | `"ai-function"` | AlgoVoi resource identifier |

---

## Method reference

### `check(headers[, body])` → `DSPyResult`

Verify payment proof from request headers.

```python
result = gate.check(dict(request.headers), request.get_json() or {})
result.requires_payment  # True → return 402; False → proceed
result.error             # human-readable rejection reason
result.as_wsgi_response()  # (status_int, headers_list, body_bytes)
result.as_flask_response() # Flask Response object
```

### `complete(messages)` → `str`

Convert an OpenAI-format message list to a prompt and run it through a DSPy `Predict` module scoped to `self._model` via `dspy.context`.

```python
reply = gate.complete([
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "What is DSPy?"},
    {"role": "assistant", "content": "DSPy is..."},
    {"role": "user",      "content": "Give me an example."},
])
```

### `run_module(module, **kwargs)` → `str`

Gate any pre-built DSPy module or compiled program. Runs `module(**kwargs)` inside `dspy.context(lm=...)`.

```python
answer = gate.run_module(my_cot_module, question="What is 2+2?")
```

Returns the first string-valued non-private output field of the Prediction, or `str(result)`.

### `as_tool(resource_fn, ...)` → `AlgoVoiPaymentTool`

Return a plain callable compatible with `dspy.ReAct`. DSPy reads `tool.__name__` and `tool.__doc__` for tool registration.

```python
tool = gate.as_tool(
    resource_fn=my_handler,
    tool_name="premium_kb",
    tool_description="Access premium content.",
)
react = dspy.ReAct(MySig, tools=[tool])
```

### `flask_guard()` → Flask `Response`

One-call Flask handler: `check()` + `complete()`.

```python
@app.route("/ai/chat", methods=["POST"])
def chat():
    return gate.flask_guard()
```

---

## Supported DSPy model providers

DSPy uses `"provider/model"` strings and reads standard environment variables for credentials.

| Provider | Model string example | Credential env var |
|----------|---------------------|-------------------|
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-opus-4-5` | `ANTHROPIC_API_KEY` |
| Google | `google/gemini-2.0-flash` | `GOOGLE_API_KEY` |
| Cohere | `cohere/command-r-plus` | `COHERE_API_KEY` |
| Groq | `groq/llama-3.1-70b-versatile` | `GROQ_API_KEY` |
| Ollama | `ollama_chat/llama3` | — (local) |
| Azure OpenAI | `azure/gpt-4o` | `AZURE_OPENAI_API_KEY` |

Pass `openai_key=` and/or `base_url=` to override credentials and endpoint at construction time.

---

## Smoke test

```bash
# Phase 1 — CI-safe (no live API needed):
python smoke_test_dspy.py --phase 1

# Phase 2 — live on-chain verification:
ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... OPENAI_KEY=sk-... \
    python smoke_test_dspy.py --phase 2
```

---

Licensed under the [Business Source License 1.1](../../LICENSE).
