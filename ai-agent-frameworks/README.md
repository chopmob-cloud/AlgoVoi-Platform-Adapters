# AI Agent Framework Adapters for AlgoVoi

Payment-gate any AI agent framework endpoint using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

Unlike the single-provider AI Platform Adapters (`ai-adapters/`), these adapters wrap entire **orchestration frameworks** — LLM-agnostic pipelines, multi-step chains, RAG systems, and autonomous agents. A single adapter gates whatever model or chain the framework uses underneath.

---

## Adapters

| Framework | Folder | Class | Agent-native | Status |
|-----------|--------|-------|-------------|--------|
| **LangChain** | [langchain/](./langchain/) | `AlgoVoiLangChain` + `AlgoVoiPaymentTool` | Yes — `BaseTool` subclass, ReAct-compatible | **Available** — 76/77 tests, Phase 1 + 2 PASS 5/5 (16 Apr 2026, Comet-validated) |
| **LlamaIndex** | [llamaindex/](./llamaindex/) | `AlgoVoiLlamaIndex` + `AlgoVoiPaymentTool` | Yes — `BaseTool` + `ToolOutput`, ReAct-compatible | **Available** — 80/80 tests (16 Apr 2026, Comet-validated) |

**Planned** (one at a time):

| Framework | Notes |
|-----------|-------|
| **CrewAI** | Gate multi-agent crew tasks |
| **AutoGen** | Gate AutoGen conversation flows |
| **Semantic Kernel** | Gate SK functions and planners (.NET / Python) |
| **Hugging Face `transformers`** | Gate inference pipelines and `InferenceClient` calls |

---

## How agent-native integration works

Each framework adapter ships two integration surfaces:

### 1. Server-side gate (Flask / FastAPI)
Same pattern as every other AlgoVoi adapter — `check()` → 402 challenge → verified → `complete()` / `invoke_chain()`:

```
Client POST → gate.check() → 402 + challenge header
Client pays on-chain, re-sends with proof
→ gate.check() returns verified
→ gate.complete(messages)  or  gate.invoke_chain(chain, inputs)
→ 200 response
```

### 2. Agent tool (LangChain `BaseTool` / CrewAI tool / etc.)
The framework's native tool abstraction wraps the payment gate. The LLM itself can trigger payment verification as part of its reasoning loop:

```
Agent selects payment tool
→ tool._run({"query": "...", "payment_proof": "<base64>"})
→ returns challenge JSON if proof absent
→ returns resource_fn(query) result if proof verified
```

---

## Shared interface

All framework adapters follow the same surface as the AI platform adapters:

| Method | Description |
|--------|-------------|
| `check(headers[, body])` | Verify payment proof — returns `LangChainResult` (or equivalent) |
| `complete(messages)` | Call the underlying LLM after gate passes |
| `invoke_chain(chain, inputs)` | Gate any framework Runnable / pipeline |
| `as_tool(resource_fn, ...)` | Return a framework-native tool wrapping the gate |
| `flask_guard()` | Convenience Flask handler — check + complete in one call |

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

## Quick start (LangChain)

```python
from langchain_algovoi import AlgoVoiLangChain

gate = AlgoVoiLangChain(
    openai_key        = "sk-...",          # OpenAI key (or pass llm= directly)
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",             # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,             # 0.01 USDC per call
)

# Gate any ChatModel — not just OpenAI
from langchain_anthropic import ChatAnthropic
gate = AlgoVoiLangChain(
    algovoi_key    = "algv_...",
    tenant_id      = "...",
    payout_address = "...",
    llm            = ChatAnthropic(model="claude-opus-4-5"),
)

# Gate any LCEL chain
result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.invoke_chain(chain, {"question": body["question"]})

# Drop into a ReAct agent
tool = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")
agent = create_react_agent(llm, tools=[tool], prompt=prompt)
```

See [langchain/README.md](./langchain/README.md) for the full reference.

---

Licensed under the [Business Source License 1.1](../LICENSE).
