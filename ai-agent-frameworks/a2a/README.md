# Google A2A Adapter for AlgoVoi

Payment-gate any Google A2A (Agent-to-Agent) endpoint using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — Python. Model-agnostic. Works with any LLM backend. Full JSON-RPC 2.0 server + A2A client. Designed for Flask.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends A2A message/send request
        |
        v
AlgoVoiA2A.flask_agent() — no payment proof
        |
        v
HTTP 402 + protocol challenge header
  x402:  X-PAYMENT-REQUIRED (spec v1, base64 JSON)
  MPP:   WWW-Authenticate: Payment (IETF draft)
  AP2:   X-AP2-Cart-Mandate (crypto-algo extension)
        |
        v
Client pays on-chain (Algorand / VOI / Hedera / Stellar)
Client re-sends with proof in Authorization header
        |
        v
AlgoVoiA2A.flask_agent() — proof verified via public
blockchain indexers (no central API dependency)
        |
        v
handle_request() routes JSON-RPC 2.0:
  message/send  → message_handler(text) → completed task
  tasks/get     → task status from internal store
  tasks/cancel  → mark task canceled
        |
        v
JSON-RPC 2.0 response — 200 OK
```

### Agent card discovery

```
GET /.well-known/agent-card.json
        |
        v
AgentCard JSON — name, url, capabilities, skills
        |
        v
A2A clients discover this agent and can call it
```

### A2A client mode

```
AlgoVoiA2A.send_message(agent_url, text)
        |
        v
POST agent_url — JSON-RPC message/send + optional Authorization header
  → if 402: returns error dict with challenge_headers
  → if 200: returns JSON-RPC result dict (task)
```

---

## Files

| File | Description |
|------|-------------|
| `a2a_algovoi.py` | Adapter — `AlgoVoiA2A`, `A2AResult`, `AlgoVoiPaymentTool` |
| `test_a2a_algovoi.py` | Unit tests (all mocked, no live calls) — 84/84 |
| `smoke_test_a2a.py` | Two-phase smoke test (challenge render + real on-chain verification) |
| `example.py` | Flask server, A2A client, payment tool, multi-protocol examples |
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
pip install flask
```

```python
from a2a_algovoi import AlgoVoiA2A

gate = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    protocol="mpp",              # "mpp" | "x402" | "ap2"
    network="algorand-mainnet",
    amount_microunits=10_000,    # 0.01 USDC per call
    agent_name="My Agent",
)
```

### Flask A2A server — one-liner

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/a2a", methods=["POST"])
def a2a_endpoint():
    return gate.flask_agent(lambda text: my_llm(text))

@app.route("/.well-known/agent-card.json")
def card():
    return jsonify(gate.agent_card("https://myhost.com/a2a"))
```

### Manual check + handle_request

```python
@app.route("/a2a", methods=["POST"])
def a2a_manual():
    guard = gate.flask_guard()
    if guard is not None:
        return guard          # 402 + challenge header

    from flask import request, jsonify
    body = request.get_json(force=True) or {}
    return jsonify(gate.handle_request(body, my_llm))
```

### A2A client — call another agent

```python
# First call — no proof → 402 challenge returned as JSON-RPC error
response = gate.send_message("https://other-agent.example.com/a2a", "What is AlgoVoi?")
if response["error"]["message"] == "payment_required":
    challenge = response["error"]["data"]["challenge_headers"]
    # ... pay on-chain ...
    proof = "base64-proof"

# Retry with proof → task result
response = gate.send_message(
    "https://other-agent.example.com/a2a",
    "What is AlgoVoi?",
    payment_proof=proof,
)
answer = response["result"]["artifacts"][0]["parts"][0]["text"]
```

### Payment tool for A2A pipelines

```python
tool = gate.as_tool(
    resource_fn=lambda query: fetch_from_kb(query),
    tool_name="premium_kb",
    tool_description="Access premium knowledge base. Pass query and payment_proof.",
)

# Without proof → challenge JSON
out = tool(query="anything", payment_proof="")
# → {"error": "payment_required", "detail": "..."}

# With verified proof → resource_fn result
out = tool(query="AlgoVoi?", payment_proof="valid-proof")
# → "KB answer for: AlgoVoi?"
```

---

## Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | `str` | required | `algv_...` API key |
| `tenant_id` | `str` | required | AlgoVoi tenant UUID |
| `payout_address` | `str` | required | On-chain payout address |
| `protocol` | `str` | `"mpp"` | Payment protocol: `"mpp"`, `"x402"`, `"ap2"` |
| `network` | `str` | `"algorand-mainnet"` | Blockchain network |
| `amount_microunits` | `int` | `10000` | Micro-USDC per call (10000 = $0.01) |
| `resource_id` | `str` | `"ai-function"` | AlgoVoi resource identifier |
| `agent_name` | `str` | `"AlgoVoi Agent"` | Agent display name |
| `agent_description` | `str` | `"Payment-gated AI agent..."` | Agent description |
| `agent_version` | `str` | `"1.0.0"` | Agent version string |

---

## Method reference

### `check(headers[, body])` → `A2AResult`

Verify payment proof from request headers.

```python
result = gate.check(dict(request.headers), body)
result.requires_payment     # True → send 402; False → proceed
result.error                # human-readable rejection reason
result.as_wsgi_response()   # (status_code, headers_list, body_bytes)
result.as_flask_response()  # Flask Response (status 402)
```

### `send_message(agent_url, text[, payment_proof, message_id, timeout])` → `dict`

Send a `message/send` request to another A2A agent. HTTPS only.

Returns a JSON-RPC 2.0 response dict: `result` on success, `error` on failure. A 402 from the remote agent is returned as `error.code == -32000` with challenge headers in `error.data.challenge_headers`.

### `handle_request(body, message_handler[, headers])` → `dict`

Route an incoming JSON-RPC 2.0 request. Dispatches `message/send` to `message_handler(text: str) → str`, manages task state for `tasks/get` and `tasks/cancel`.

If `headers` are provided, payment is verified first.

### `agent_card(agent_url[, skills, supports_streaming, supports_push])` → `dict`

Generate a compliant A2A AgentCard dict for `/.well-known/agent-card.json`.

### `as_tool(resource_fn[, tool_name, tool_description])` → `AlgoVoiPaymentTool`

Return a payment-gated callable for use inside A2A agent pipelines.

### `flask_guard()` → `Flask Response | None`

Payment-check-only handler. Returns 402 Flask Response if payment required, `None` otherwise.

### `flask_agent(message_handler)` → `Flask Response`

Full A2A Flask endpoint: payment check + JSON-RPC routing. Use for `POST /a2a`.

---

## A2A protocol notes

### Agent card discovery

Serve `agent_card()` output at `GET /.well-known/agent-card.json`. A2A clients fetch this to discover the agent's capabilities before sending messages.

### JSON-RPC 2.0 methods

| Method | Description |
|--------|-------------|
| `message/send` | Send a message and wait for synchronous task result |
| `tasks/get` | Retrieve task status by task ID |
| `tasks/cancel` | Cancel a pending or running task |

### Task states

| State | Description |
|-------|-------------|
| `completed` | Task finished successfully |
| `failed` | `message_handler` raised an exception |
| `canceled` | Canceled via `tasks/cancel` |

### Message parts

The adapter extracts text from `TextPart` entries (`{"type": "text", "text": "..."}`). `FilePart` and `DataPart` are passed through in the raw `message` dict but not extracted by `_extract_text`.

---

## Smoke test

```bash
# Phase 1 — no live API needed:
python smoke_test_a2a.py --phase 1

# Phase 2 — live on-chain verification:
ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... \
  python smoke_test_a2a.py --phase 2
```

---

## Requirements

- Python ≥ 3.9
- `flask` (for `flask_guard` / `flask_agent`)
- One of:
  - `mpp-adapter/` sibling directory (for `protocol="mpp"`)
  - `ap2-adapter/` sibling directory (for `protocol="ap2"`)
  - `ai-adapters/openai/` sibling directory (for `protocol="x402"`)

---

Licensed under the [Business Source License 1.1](../../LICENSE).
