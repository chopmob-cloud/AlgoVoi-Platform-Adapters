# CrewAI Adapter for AlgoVoi

Payment-gate any CrewAI crew, task, or agent tool using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the other AlgoVoi AI framework adapters, plus CrewAI-native crew kickoff gating and `BaseTool` integration.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiCrewAI.check() — no payment proof
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
AlgoVoiCrewAI.check() — proof verified
        |
        v
gate.crew_kickoff(crew, inputs={...})  → crew.kickoff() → CrewOutput.raw
        |
        v
HTTP 200 — response returned
```

### Agent tool mode (no HTTP gateway)

```
Agent reasoning loop selects AlgoVoiPaymentTool
        |
        v
CrewAI validates {"query": "...", "payment_proof": "..."} against PaymentToolInput
        |
        v
tool._run(query="...", payment_proof="...")
  → challenge JSON if proof absent/invalid
  → resource_fn(query) if payment verified
```

---

## Files

| File | Description |
|------|-------------|
| `crewai_algovoi.py` | Adapter — `AlgoVoiCrewAI`, `AlgoVoiPaymentTool`, `CrewAIResult`, `PaymentToolInput` |
| `test_crewai_algovoi.py` | Unit tests (all mocked, no live calls) — 68/68 |
| `example.py` | Flask + FastAPI + agent deployment examples |
| `smoke_test_crewai.py` | Two-phase smoke test (challenge render + real on-chain verification) |
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
from crewai_algovoi import AlgoVoiCrewAI

gate = AlgoVoiCrewAI(
    openai_key        = "sk-...",                  # for _ensure_llm(); pass llm= to skip
    algovoi_key       = "algv_...",
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,                     # 0.01 USDC per crew run
)
```

### Flask — gate a crew.kickoff()

```python
from flask import Flask, request, jsonify
from crewai import Crew

app = Flask(__name__)

@app.route("/ai/research", methods=["POST"])
def research():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    output = gate.crew_kickoff(my_crew, inputs={"topic": body["topic"]})
    return jsonify({"content": output})
```

Or use the convenience wrapper with an inputs extractor:

```python
@app.route("/ai/research", methods=["POST"])
def research():
    return gate.flask_guard(
        my_crew,
        inputs_fn = lambda body: {"topic": body.get("topic", "")},
    )
```

### FastAPI

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

@app.post("/ai/research")
async def research(req: Request):
    body   = await req.json()
    result = gate.check(dict(req.headers), body)
    if result.requires_payment:
        status, headers, body_bytes = result.as_wsgi_response()
        return Response(body_bytes, status_code=402, headers=dict(headers))
    output = gate.crew_kickoff(my_crew, inputs={"topic": body["topic"]})
    return JSONResponse({"content": output})
```

### Bring your own LLM

Pass a pre-built `crewai.LLM` instance:

```python
from crewai import LLM

gate = AlgoVoiCrewAI(
    algovoi_key    = "algv_...",
    tenant_id      = "...",
    payout_address = "...",
    llm            = LLM(model="anthropic/claude-opus-4-5", api_key="sk-ant-..."),
)
```

### Agent tool — drop into any CrewAI agent

```python
from crewai import Agent, Task, Crew

def my_protected_fn(query: str) -> str:
    return f"Premium answer to: {query}"

tool = gate.as_tool(
    resource_fn      = my_protected_fn,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base.",
)

researcher = Agent(
    role      = "Research Analyst",
    goal      = "Use premium_kb to answer the user's question.",
    backstory = "Expert researcher with access to premium data sources.",
    tools     = [tool],
    llm       = my_llm,
)
```

The agent generates structured input validated against `PaymentToolInput`:

| Field | Type | Description |
|-------|------|-------------|
| `query` | Any | Question or task for the protected resource |
| `payment_proof` | str | Base64-encoded payment proof (empty → challenge returned) |

`_run(query, payment_proof)` receives these as kwargs directly (CrewAI unpacks from Pydantic model).

---

## CrewOutput — returned by crew_kickoff()

`gate.crew_kickoff(crew, inputs)` returns `crew_output.raw` (a string). Full `CrewOutput` fields:

| Field | Type | Description |
|-------|------|-------------|
| `raw` | str | Final string output from the last task |
| `pydantic` | BaseModel | Structured output if `output_pydantic` set on final task |
| `json_dict` | dict | JSON-formatted output |
| `tasks_output` | list | Individual outputs from each task |
| `token_usage` | dict | LLM token metrics |

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `openai_key` | str | `None` | OpenAI key — passed to `crewai.LLM` if `llm=` not supplied |
| `llm` | Any | `None` | Pre-built `crewai.LLM` instance (takes precedence) |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per crew run in USDC microunits (10000 = 0.01 USDC) |
| `model` | str | `"openai/gpt-4o"` | LiteLLM model identifier (e.g. `"anthropic/claude-opus-4-5"`) |
| `base_url` | str | `None` | Override API base URL (for compatible providers) |
| `resource_id` | str | `"ai-crew"` | Resource identifier used in MPP challenges |

---

## Supported model providers (via LiteLLM)

Pass `model=` in LiteLLM format. Any provider supported by `crewai.LLM` works:

| Provider | model= example |
|----------|---------------|
| OpenAI | `openai/gpt-4o` (default) |
| Anthropic | `anthropic/claude-opus-4-5` |
| Google Gemini | `gemini/gemini-2.0-flash` |
| AWS Bedrock | `bedrock/amazon.nova-pro-v1:0` |
| Together AI | `together_ai/mistralai/Mixtral-8x7B` |
| Groq | `groq/llama3-8b-8192` |

---

## Dependencies

```
crewai>=0.80.0      # pip install crewai
pydantic>=2.0       # pip install pydantic   (included with crewai)
```

x402 gate reused from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
