# AutoGen Adapter for AlgoVoi

Payment-gate any AutoGen conversation or callable tool using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — same API surface as the other AlgoVoi AI framework adapters, plus AutoGen `initiate_chat()` gating, `llm_config` property, and `FunctionTool`-compatible callable tool.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiAutoGen.check() — no payment proof
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
AlgoVoiAutoGen.check() — proof verified
        |
        v
gate.initiate_chat(recipient, sender, message)
  → sender.initiate_chat(recipient, message=..., max_turns=...)
  → ChatResult.summary or last chat_history message
        |
        v
HTTP 200 — response returned
```

### Callable tool mode (no HTTP gateway)

```
Agent reasoning loop invokes AlgoVoiPaymentTool
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
| `autogen_algovoi.py` | Adapter — `AlgoVoiAutoGen`, `AlgoVoiPaymentTool`, `AutoGenResult`, `_extract_chat_result` |
| `test_autogen_algovoi.py` | Unit tests (all mocked, no live calls) — 86/86 |
| `example.py` | Flask + FastAPI + 0.2.x tool + 0.4.x FunctionTool + GroupChat examples |
| `smoke_test_autogen.py` | Two-phase smoke test (challenge render + real on-chain verification) |
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
from autogen_algovoi import AlgoVoiAutoGen

gate = AlgoVoiAutoGen(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,                     # 0.01 USDC per conversation
    model             = "gpt-4o",
)
```

### Build AutoGen agents using `gate.llm_config`

```python
from autogen import AssistantAgent, UserProxyAgent

assistant = AssistantAgent(
    name       = "assistant",
    llm_config = gate.llm_config,
    # expands to: {"config_list": [{"model": "gpt-4o", "api_key": "sk-..."}]}
)

user_proxy = UserProxyAgent(
    name             = "user_proxy",
    human_input_mode = "NEVER",
    max_consecutive_auto_reply = 3,
    code_execution_config      = False,
)
```

### Flask — gate a conversation

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    output = gate.initiate_chat(
        recipient = assistant,
        sender    = user_proxy,
        message   = body.get("message", ""),
        max_turns = 5,
    )
    return jsonify({"content": output})
```

Or use the convenience one-liner:

```python
@app.route("/ai/chat", methods=["POST"])
def chat():
    return gate.flask_guard(
        sender     = user_proxy,
        recipient  = assistant,
        message_fn = lambda b: b.get("message", ""),
        max_turns  = 5,
    )
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
    output = gate.initiate_chat(
        recipient = assistant,
        sender    = user_proxy,
        message   = body.get("message", ""),
    )
    return JSONResponse({"content": output})
```

### AutoGen 0.2.x — callable tool

```python
def my_protected_fn(query: str) -> str:
    return f"Premium answer to: {query}"

tool = gate.as_tool(
    resource_fn      = my_protected_fn,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base.",
)

@user_proxy.register_for_execution()
@assistant.register_for_llm(description=tool.description, name=tool.name)
def premium_kb(query: str, payment_proof: str = "") -> str:
    return tool(query=query, payment_proof=payment_proof)
```

### AutoGen 0.4.x — `FunctionTool`

```python
from autogen_core.tools import FunctionTool
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

tool    = gate.as_tool(resource_fn=my_handler, tool_name="premium_kb")
fn_tool = FunctionTool(tool, description=tool.description, name=tool.name)

model_client = OpenAIChatCompletionClient(model="gpt-4o", api_key="sk-...")
agent = AssistantAgent("assistant", tools=[fn_tool], model_client=model_client)
```

The agent passes `query` and `payment_proof` (base64) to `tool(...)`. Returns challenge JSON if proof absent/invalid; calls `resource_fn(query)` and returns the result if verified.

### GroupChat

```python
from autogen import GroupChat, GroupChatManager

group   = GroupChat(agents=[assistant, user_proxy], messages=[], max_round=6)
manager = GroupChatManager(groupchat=group, llm_config=gate.llm_config)

# Gate the GroupChat conversation just like a two-agent chat:
output = gate.initiate_chat(
    recipient = manager,
    sender    = user_proxy,
    message   = "Discuss the quarterly results.",
    max_turns = 6,
)
```

---

## `ChatResult` extraction

`gate.initiate_chat()` returns the conversation result as a plain string. Extraction priority:

| Priority | Source | Notes |
|----------|--------|-------|
| 1 | `ChatResult.summary` | Set when `summary_method` is configured on agents |
| 2 | Last entry in `ChatResult.chat_history` | `history[-1]["content"]` |
| 3 | `str(ChatResult)` | Fallback |

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `openai_key` | str | `None` | OpenAI API key — used to build `llm_config` |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per conversation in USDC microunits |
| `model` | str | `"gpt-4o"` | Model ID included in `llm_config` |
| `base_url` | str | `None` | Override API base URL (for Azure, compatible providers) |
| `resource_id` | str | `"ai-conversation"` | Resource identifier used in MPP challenges |

---

## Method reference

| Method | Description |
|--------|-------------|
| `check(headers[, body])` | Verify payment proof — returns `AutoGenResult` |
| `initiate_chat(recipient, sender, message, ...)` | Gate + run a conversation — returns `str` |
| `llm_config` | Property — AutoGen `{"config_list": [...]}` dict built from `openai_key` / `model` |
| `as_tool(resource_fn, ...)` | Return callable `AlgoVoiPaymentTool` for agent tool registration |
| `flask_guard(sender, recipient, ...)` | Convenience Flask handler — check + chat in one call |

---

## Dependencies

```
pyautogen>=0.2.0    # pip install pyautogen  (AutoGen 0.2.x)
# OR
autogen-agentchat   # pip install autogen-agentchat  (AutoGen 0.4.x)
flask               # pip install flask  (for flask_guard)
```

x402 gate reused from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
