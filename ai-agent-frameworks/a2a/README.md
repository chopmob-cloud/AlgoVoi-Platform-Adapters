# Google A2A Adapter for AlgoVoi

Payment-gate any Google A2A (Agent-to-Agent) endpoint using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v2.0.0 — Python. Model-agnostic. Works with any LLM backend. A2A v1.0 REST server + client. Designed for Flask.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends POST /message:send
        |
        v
AlgoVoiA2A.flask_message_send() — no payment proof
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
AlgoVoiA2A.flask_message_send() — proof verified via public
blockchain indexers (no central API dependency)
        |
        v
message_handler(text) → completed task dict returned directly
```

### Agent card discovery

```
GET /.well-known/agent.json          → base AgentCard
GET /extendedAgentCard               → base card + authentication + endpoints
        |
        v
A2A clients discover agent name, capabilities, skills,
supported payment schemes, networks, and REST endpoint URLs
```

### A2A client mode

```
AlgoVoiA2A.send_message(agent_url, text)
        |
        v
POST {agent_url}/message:send
  payload: {"message": {"role": "user", "parts": [...], "messageId": "..."}}
  → if 402: returns {"error": "payment_required", "challenge_headers": {...}, "request_id": "..."}
  → if 200: returns task dict directly (A2A v1.0 REST — no JSON-RPC wrapper)
```

---

## Files

| File | Description |
|------|-------------|
| `a2a_algovoi.py` | Adapter — `AlgoVoiA2A`, `A2AResult`, `AlgoVoiPaymentTool` |
| `test_a2a_algovoi.py` | Unit tests (all mocked, no live calls) — 120/120 |
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
    api_base="https://cloud.algovoi.co.uk",   # AlgoVoi payment backend
)
```

### Flask A2A v1.0 REST server

```python
from flask import Flask, jsonify

app = Flask(__name__)

AGENT_URL = "https://myhost.com"

# Agent card discovery — public, no auth
@app.route("/.well-known/agent.json")
def agent_card():
    return jsonify(gate.flask_agent_card(AGENT_URL))

# Extended agent card — payment auth required
@app.route("/extendedAgentCard")
def extended_card():
    return gate.flask_extended_agent_card(AGENT_URL)

# Message endpoint — payment-gated
@app.route("/message:send", methods=["POST"])
def message_send():
    return gate.flask_message_send(lambda text: my_llm(text))

# Task list + individual task
@app.route("/tasks")
def list_tasks():
    return gate.flask_list_tasks()

@app.route("/tasks/<task_id>")
def get_task(task_id):
    return gate.flask_get_task(task_id)

@app.route("/tasks/<task_id>:cancel", methods=["POST"])
def cancel_task(task_id):
    return gate.flask_cancel_task(task_id)
```

### Flask REST routes at a glance

| Method | Path | Auth | Handler |
|--------|------|------|---------|
| `GET` | `/.well-known/agent.json` | None | `flask_agent_card(agent_url)` |
| `GET` | `/extendedAgentCard` | Payment | `flask_extended_agent_card(agent_url)` |
| `POST` | `/message:send` | Payment | `flask_message_send(message_handler)` |
| `GET` | `/tasks` | None | `flask_list_tasks()` |
| `GET` | `/tasks/<id>` | None | `flask_get_task(task_id)` |
| `POST` | `/tasks/<id>:cancel` | None | `flask_cancel_task(task_id)` |

### Manual check + handle_request (legacy JSON-RPC compat)

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
# First call — no proof → 402 error dict returned
response = gate.send_message("https://other-agent.example.com", "What is AlgoVoi?")
if response.get("error") == "payment_required":
    challenge = response["challenge_headers"]
    # ... pay on-chain ...
    proof = "base64-proof"

# Retry with proof → task dict returned directly
response = gate.send_message(
    "https://other-agent.example.com",
    "What is AlgoVoi?",
    payment_proof=proof,
)
answer = response["artifacts"][0]["parts"][0]["text"]
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
| `api_base` | `str` | `"https://cloud.algovoi.co.uk"` | AlgoVoi payment backend URL |

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

Send a REST `POST {agent_url}/message:send` request to another A2A v1.0 agent. HTTPS only.

- **200** → returns the task dict directly (A2A v1.0 REST — no JSON-RPC wrapper). Access result via `response["artifacts"][0]["parts"][0]["text"]`.
- **402** → returns `{"error": "payment_required", "challenge_headers": {...}, "request_id": "..."}`.

### `handle_request(body, message_handler[, headers])` → `dict`

Route an incoming JSON-RPC 2.0 request (legacy compat). Dispatches `message/send` to `message_handler(text: str) → str`, manages task state for `tasks/get` and `tasks/cancel`.

If `headers` are provided, payment is verified first.

### `agent_card(agent_url[, skills, supports_streaming, supports_push])` → `dict`

Generate a compliant A2A AgentCard dict for `GET /.well-known/agent.json`.

### `extended_agent_card(agent_url[, ...])` → `dict`

Returns the base agent card extended with `authentication` (supported schemes, protocols, networks, currency, amount_microunits) and `endpoints` (all 6 REST route URLs).

### `list_tasks()` → `list`

Return all tasks in reverse-creation order.

### `as_tool(resource_fn[, tool_name, tool_description])` → `AlgoVoiPaymentTool`

Return a payment-gated callable for use inside A2A agent pipelines.

### `flask_guard()` → `Flask Response | None`

Payment-check-only handler. Returns 402 Flask Response if payment required, `None` otherwise.

### `flask_agent_card(agent_url[, ...])` → `Flask Response`

Serve `agent_card()` as a public JSON response for `GET /.well-known/agent.json`.

### `flask_extended_agent_card(agent_url[, ...])` → `Flask Response`

Payment-gated extended card. Calls `flask_guard()` first; returns 402 if unpaid.

### `flask_message_send(message_handler)` → `Flask Response`

Full A2A v1.0 REST message endpoint: payment check + dispatch. Returns the task dict directly (200 OK) or 402 challenge. Use for `POST /message:send`.

### `flask_list_tasks()` → `Flask Response`

Returns `{"tasks": [...]}` — all tasks newest-first.

### `flask_get_task(task_id)` → `Flask Response`

Returns the task dict for `task_id`, or 404 if not found.

### `flask_cancel_task(task_id)` → `Flask Response`

Marks `task_id` as canceled and returns the updated task dict, or 404 if not found.

### `flask_agent(message_handler)` → `Flask Response`

Legacy JSON-RPC 2.0 full endpoint: payment check + JSON-RPC routing. Use for `POST /a2a` (backward compat).

---

## A2A protocol notes

### Agent card discovery

Serve `agent_card()` output at `GET /.well-known/agent.json`. A2A clients fetch this to discover the agent's capabilities before sending messages. Serve `extended_agent_card()` at `GET /extendedAgentCard` for clients that need payment details and endpoint URLs.

### A2A v1.0 REST endpoints

| Route | Description |
|-------|-------------|
| `GET /.well-known/agent.json` | Public agent card |
| `GET /extendedAgentCard` | Extended card with auth + endpoints (payment-gated) |
| `POST /message:send` | Send a message and wait for synchronous task result |
| `GET /tasks` | List all tasks (newest-first) |
| `GET /tasks/{id}` | Retrieve task status by task ID |
| `POST /tasks/{id}:cancel` | Cancel a pending or running task |

### Legacy JSON-RPC 2.0 methods (backward compat)

| Method | Description |
|--------|-------------|
| `message/send` | Send a message and wait for synchronous task result |
| `tasks/get` | Retrieve task status by task ID |
| `tasks/cancel` | Mark task canceled |

### Task states

| State | Description |
|-------|-------------|
| `completed` | Task finished successfully |
| `failed` | `message_handler` raised an exception |
| `canceled` | Canceled via `tasks/{id}:cancel` or `tasks/cancel` |

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
- `flask` (for `flask_guard` / `flask_message_send` / `flask_agent`)
- One of:
  - `mpp-adapter/` sibling directory (for `protocol="mpp"`)
  - `ap2-adapter/` sibling directory (for `protocol="ap2"`)
  - `ai-adapters/openai/` sibling directory (for `protocol="x402"`)

---

Licensed under the [Business Source License 1.1](../../LICENSE).
