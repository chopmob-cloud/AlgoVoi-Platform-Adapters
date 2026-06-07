# LangGraph Adapter for AlgoVoi

Payment-gate any LangGraph compiled StateGraph using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

**v1.0.0 — gate `graph.invoke()` / `graph.stream()` endpoints and drop `AlgoVoiPaymentTool` into any LangGraph ToolNode or `create_react_agent`.**

https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## How it works

```
Client sends request
        |
        v
AlgoVoiLangGraph.check() — no payment proof
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
AlgoVoiLangGraph.check() — proof verified
        |
        v
gate.invoke_graph(graph, inputs)            → compiled graph, returns final state
gate.stream_graph(graph, inputs, mode=...)  → compiled graph, yields chunks
        |
        v
HTTP 200 — response returned
```

---

## Files

| File | Description |
|------|-------------|
| `langgraph_algovoi.py` | Adapter — `AlgoVoiLangGraph`, `AlgoVoiPaymentTool`, `LangGraphResult` |
| `test_langgraph_algovoi.py` | Unit tests (all mocked, no live calls) |
| `example.py` | Flask + FastAPI + ToolNode + custom graph examples |
| `smoke_test_langgraph.py` | Two-phase smoke test (challenge render + real on-chain verification) |
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
from langgraph_algovoi import AlgoVoiLangGraph

gate = AlgoVoiLangGraph(
    algovoi_key       = "algv_...",                # AlgoVoi API key
    tenant_id         = "<your-tenant-uuid>",
    payout_address    = "<your-algorand-address>",
    protocol          = "mpp",                     # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",        # see table above
    amount_microunits = 10000,                     # 0.01 USDC per call
)
```

### Flask — manual check + invoke

```python
from flask import Flask, request, jsonify, Response
app = Flask(__name__)

@app.route("/agent", methods=["POST"])
def agent():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        flask_body, status, headers = result.as_flask_response()
        return Response(flask_body, status=status, headers=headers,
                        mimetype="application/json")
    output = gate.invoke_graph(compiled_graph, {"messages": body["messages"]})
    return jsonify(output)
```

### Flask — convenience wrappers

```python
# flask_agent: check + invoke in one call
@app.route("/agent", methods=["POST"])
def agent():
    return gate.flask_agent(compiled_graph)

# flask_guard: check only, caller runs the graph
@app.route("/agent", methods=["POST"])
def agent():
    guard = gate.flask_guard()
    if guard is not None:
        return guard           # 402
    output = gate.invoke_graph(compiled_graph, request.get_json()["inputs"])
    return jsonify(output)
```

### FastAPI

```python
from fastapi import FastAPI, Request
from fastapi.responses import Response

app = FastAPI()

@app.post("/agent")
async def agent(req: Request):
    body   = await req.json()
    result = gate.check(dict(req.headers), body)
    if result.requires_payment:
        _, headers, body_bytes = result.as_wsgi_response()
        return Response(body_bytes, status_code=402, headers=dict(headers))
    output = gate.invoke_graph(compiled_graph, {"messages": body["messages"]})
    return output
```

### Streaming

```python
# stream_mode: "values" (full state), "updates" (node delta), "messages" (tokens)
for chunk in gate.stream_graph(compiled_graph, {"messages": [...]},
                               stream_mode="updates"):
    print(chunk)
```

### ToolNode (ReAct agent)

Drop the payment gate into a LangGraph `create_react_agent`:

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

def my_kb(query: str) -> str:
    return f"Premium answer: {query}"

tool  = gate.as_tool(resource_fn=my_kb, tool_name="premium_kb")
llm   = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, [tool])
```

### Custom StateGraph with ToolNode

```python
node = gate.tool_node(resource_fn=my_kb, tool_name="premium_kb")

graph = StateGraph(State)
graph.add_node("agent", agent_node)
graph.add_node("tools", node)          # payment-gated tool node
graph.add_conditional_edges("agent", should_use_tools)
graph.add_edge("tools", "agent")
compiled = graph.compile()
```

The tool returns challenge JSON if the proof is missing or invalid, and the resource result when the proof is verified.

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

## LangGraph-specific features

| Method | Description |
|--------|-------------|
| `invoke_graph(graph, inputs, config=None)` | Call `graph.invoke(inputs, config=config)` — preserves checkpointing, recursion limits |
| `stream_graph(graph, inputs, config=None, stream_mode="values")` | Yield from `graph.stream(...)` with configurable mode |
| `as_tool(resource_fn, ...)` | Return `AlgoVoiPaymentTool` (`BaseTool` subclass) for ToolNode / ReAct |
| `tool_node(resource_fn, ...)` | Return `langgraph.prebuilt.ToolNode([tool])` ready to add as a graph node |
| `flask_guard()` | Payment-check-only Flask handler — returns 402 or `None` |
| `flask_agent(graph, input_key="messages")` | Combined check + invoke Flask handler |

---

## Constructor reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `algovoi_key` | str | required | AlgoVoi API key (`algv_...`) |
| `tenant_id` | str | required | AlgoVoi tenant UUID |
| `payout_address` | str | required | On-chain address to receive payments |
| `protocol` | str | `"mpp"` | Payment protocol — `"mpp"`, `"ap2"`, or `"x402"` |
| `network` | str | `"algorand-mainnet"` | Chain network key |
| `amount_microunits` | int | `10000` | Price per call in USDC microunits (10000 = 0.01 USDC) |
| `resource_id` | str | `"ai-function"` | Resource identifier used in MPP challenges |

---

## Dependencies

```
langchain-core>=0.1.0   # pip install langchain-core  (for AlgoVoiPaymentTool / BaseTool)
langgraph>=0.1.0        # pip install langgraph        (for tool_node())
pydantic>=2.0           # pip install pydantic         (for _PaymentInput schema)
```

x402 gate reused inline from `ai-adapters/openai/openai_algovoi.py`.
MPP and AP2 gates require the sibling `mpp-adapter/` and `ap2-adapter/` directories.

`langchain-core` is only required for `AlgoVoiPaymentTool` — the adapter stubs it
gracefully if not installed; `check()`, `invoke_graph()`, `stream_graph()`,
`flask_guard()`, and `flask_agent()` work without it.

`langgraph` is only required for `tool_node()` — it is imported lazily and raises
a clear `ImportError` if missing.

---

Licensed under the [Business Source License 1.1](../../LICENSE).
