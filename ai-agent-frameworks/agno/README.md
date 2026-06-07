# AlgoVoi Agno Adapter

Payment-gate any [Agno](https://github.com/agno-agi/agno) agent using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

## Overview

Agno (formerly Phidata, ~39k GitHub stars) is a multi-modal AI agent framework featuring a hook system, AgentOS production runtime (FastAPI-based), and a rich tool ecosystem. This adapter gates Agno agents behind on-chain payment verification with three integration surfaces.

## Quick start

```python
from agno_algovoi import AlgoVoiAgno

gate = AlgoVoiAgno(
    algovoi_key="algv_...",
    tenant_id="your-tenant-id",
    payout_address="YOUR_WALLET_ADDRESS",
    protocol="mpp",
    network="algorand-mainnet",
    amount_microunits=10_000,   # $0.01 USDC
)
```

### Pattern 1 — Direct check + `agent.run()`

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(model=OpenAIChat(id="gpt-4o"))

# Flask route
@app.route("/ask", methods=["POST"])
def ask():
    result = gate.check(dict(request.headers), request.get_json())
    if result.requires_payment:
        return result.as_flask_response()   # 402 + payment challenge

    output = agent.run(request.json["message"])
    return jsonify({"response": output.content})
```

### Pattern 2 — `run_agent()` wrapper

```python
from agno_algovoi import AgnoPaymentRequired

@app.route("/ask", methods=["POST"])
def ask():
    try:
        output = gate.run_agent(agent, request.json["message"],
                                headers=dict(request.headers))
        return jsonify({"response": output.content})
    except AgnoPaymentRequired as exc:
        return exc.result.as_flask_response()   # 402
```

### Pattern 2b — `flask_agent()` one-liner

```python
@app.route("/ask", methods=["POST"])
def ask():
    return gate.flask_agent(agent)
```

### Pattern 3 — Agno pre-hook

Captures payment headers at request time and injects them into Agno's native hook lifecycle.

```python
@app.route("/ask", methods=["POST"])
def ask():
    body = request.get_json() or {}
    hook = gate.make_pre_hook(headers=dict(request.headers), body=body)

    agent = Agent(model=OpenAIChat(id="gpt-4o"), pre_hooks=[hook])
    try:
        output = agent.run(body.get("message", ""))
        return jsonify({"response": output.content})
    except AgnoPaymentRequired as exc:
        return exc.result.as_flask_response()
```

### Pattern 4 — FastAPI / AgentOS middleware

Gates all routes on an AgentOS-managed FastAPI app via ASGI middleware.

```python
from agno.os import AgentOS

agent_os = AgentOS(agents=[my_agent])
app      = agent_os.get_app()

gate.fastapi_middleware(app)   # all routes now require payment

# uvicorn example:app --reload
```

### Pattern 5 — Async FastAPI

```python
from agno_algovoi import AgnoPaymentRequired

@app.post("/ask")
async def ask(request: Request):
    body = await request.json()
    try:
        output = await gate.arun_agent(
            agent, body["message"],
            headers=dict(request.headers),
        )
        return {"response": output.content}
    except AgnoPaymentRequired as exc:
        status, hdrs, body_bytes = exc.result.as_wsgi_response()
        return Response(content=body_bytes, status_code=402, headers=dict(hdrs))
```

## API reference

### `AlgoVoiAgno(algovoi_key, tenant_id, payout_address, ...)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | `str` | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | `str` | required | AlgoVoi tenant ID |
| `payout_address` | `str` | required | Wallet address to receive payments |
| `protocol` | `str` | `"mpp"` | `"mpp"`, `"x402"`, or `"ap2"` |
| `network` | `str` | `"algorand-mainnet"` | See networks table below |
| `amount_microunits` | `int` | `10_000` | Payment amount ($0.01 USDC = 10,000) |
| `resource_id` | `str` | `"ai-function"` | Logical resource ID for MPP challenges |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `check(headers, body=None)` | `AgnoResult` | Verify payment proof |
| `run_agent(agent, message, headers, body=None)` | agent output | Gate then `agent.run(message)` |
| `arun_agent(agent, message, headers, body=None)` | coroutine | Gate then `await agent.arun(message)` |
| `make_pre_hook(headers, body=None)` | `Callable` | Returns hook for `Agent(pre_hooks=[...])` |
| `fastapi_middleware(app)` | `app` | Add ASGI payment middleware to FastAPI |
| `flask_guard()` | tuple or `None` | `(body, 402, headers)` or `None` |
| `flask_agent(agent, message_key="message")` | Flask response | Full endpoint — check + `agent.run()` |

### `AgnoResult`

| Attribute | Type | Description |
|-----------|------|-------------|
| `requires_payment` | `bool` | `True` if caller must pay |
| `receipt` | `MppReceipt \| None` | MPP receipt on success |
| `mandate` | `Ap2Mandate \| None` | AP2 mandate on success |
| `error` | `str \| None` | Error message if verification failed |
| `as_flask_response()` | `(body, 402, headers)` | Flask-compatible 402 response |
| `as_wsgi_response()` | `(status, headers, body)` | WSGI 3-tuple |

### `AgnoPaymentRequired`

Raised by `run_agent()`, `arun_agent()`, and `make_pre_hook()` callbacks when payment proof is absent or invalid.

| Attribute | Description |
|-----------|-------------|
| `result` | The `AgnoResult` that triggered the exception |

## Agno-specific features

| Feature | How it works |
|---------|-------------|
| Pre-hook injection | `make_pre_hook()` returns a callable for `Agent(pre_hooks=[...])` — raises `AgnoPaymentRequired` if proof invalid |
| ASGI middleware | `fastapi_middleware(app)` wraps `AgentOS.get_app()` — intercepts all HTTP routes |
| Async support | `arun_agent()` awaits `agent.arun()` — correct for async AgentOS endpoints |
| Non-HTTP passthrough | WebSocket / lifespan ASGI scopes bypass the middleware gate unchanged |

## Supported networks

| Network | Asset | Identifier |
|---------|-------|------------|
| Algorand | USDC | ASA 31566704 |
| VOI | aUSDC | ARC-200 302190 |
| Hedera | USDC | HTS 0.0.456858 |
| Stellar | USDC | Circle |

## Supported protocols

| Protocol | Challenge header | Use case |
|----------|-----------------|----------|
| MPP | `WWW-Authenticate: Payment ...` | Recommended — IETF standard |
| x402 | `X-PAYMENT-REQUIRED: <base64>` | HTTP-native micro-payments |
| AP2 | `X-AP2-Cart-Mandate: <base64>` | Google Agentic Payments |

## Dependencies

```
agno               # pip install agno
flask              # optional — for flask_guard / flask_agent
fastapi            # optional — for fastapi_middleware / arun_agent
```

The core adapter (`agno_algovoi.py`) has no imports from `agno` at module level — all Agno objects are passed in by the caller, so no version pinning is required.

## Tests

```bash
# Unit tests (88 tests, no network required)
python -m pytest test_agno_algovoi.py -v

# Smoke tests — Phase 1 (13 cases, no network required)
python smoke_test_agno.py --phase 1

# Smoke tests — Phase 2 (live on-chain round-trip)
ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... \
    python smoke_test_agno.py --phase 2
```

## Repository

[chopmob-cloud/AlgoVoi-Platform-Adapters](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)

Licensed under the Business Source License 1.1 — see [LICENSE](../../LICENSE) for details.
