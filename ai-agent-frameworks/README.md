# AI Agent Framework Adapters for AlgoVoi

Payment-gate any AI agent framework endpoint using x402, MPP, or AP2 — paid in USDC on Algorand, VOI, Hedera, or Stellar.

Unlike the single-provider AI Platform Adapters (`ai-adapters/`), these adapters wrap entire **orchestration frameworks** — LLM-agnostic pipelines, multi-step chains, RAG systems, and autonomous agents. A single adapter gates whatever model or chain the framework uses underneath.

---

## Adapters

| Framework | Folder | Class | Agent-native | Status |
|-----------|--------|-------|-------------|--------|
| **LangChain** | [langchain/](./langchain/) | `AlgoVoiLangChain` + `AlgoVoiPaymentTool` | Yes — `BaseTool` subclass, ReAct-compatible | **Available** — 76/77 tests, Phase 1 + 2 PASS 5/5 (16 Apr 2026, Comet-validated) |
| **LlamaIndex** | [llamaindex/](./llamaindex/) | `AlgoVoiLlamaIndex` + `AlgoVoiPaymentTool` | Yes — `BaseTool` + `ToolOutput`, ReAct-compatible | **Available** — 80/80 tests (16 Apr 2026, Comet-validated) |
| **CrewAI** | [crewai/](./crewai/) | `AlgoVoiCrewAI` + `AlgoVoiPaymentTool` | Yes — `BaseTool` with `PaymentToolInput` args_schema | **Available** — 68/68 tests (16 Apr 2026, Comet-validated) |
| **Hugging Face** | [huggingface/](./huggingface/) | `AlgoVoiHuggingFace` + `AlgoVoiPaymentTool` | Yes — `smolagents.Tool` subclass, `ToolCallingAgent`-compatible | **Available** — 83/83 tests (16 Apr 2026) |
| **AutoGen** | [autogen/](./autogen/) | `AlgoVoiAutoGen` + `AlgoVoiPaymentTool` | Yes — callable tool, 0.2.x `register_for_execution` + 0.4.x `FunctionTool`-compatible | **Available** — 86/86 tests (16 Apr 2026) |
| **Semantic Kernel** | [semantic-kernel/](./semantic-kernel/) | `AlgoVoiSemanticKernel` + `AlgoVoiPaymentPlugin` | Yes — `@kernel_function` plugin, auto-invocation compatible | **Available** — 76/76 tests (16 Apr 2026) |
| **Pydantic AI** | [pydantic-ai/](./pydantic-ai/) | `AlgoVoiPydanticAI` + `AlgoVoiPaymentTool` | Yes — plain callable `Tool`, deps injection, any provider:model string | **Available** — 77/77 tests (16 Apr 2026) |
| **DSPy** | [dspy/](./dspy/) | `AlgoVoiDSPy` + `AlgoVoiPaymentTool` | Yes — plain callable, `dspy.ReAct`-compatible, `__name__`/`__doc__` set | **Available** — 78/78 tests, Phase 1 9/9 PASS (16 Apr 2026, Comet-validated) |
| **Vercel AI SDK** | [vercel-ai-sdk/](./vercel-ai-sdk/) | `AlgoVoiVercelAI` + `VercelAIResult` | Yes — `tool()` compatible, `generateText` + `streamText` + `nextHandler` | **Available** — 79/79 tests, Phase 1 12/12 PASS (16 Apr 2026, Comet-validated) — **TypeScript** |
| **Google A2A** | [a2a/](./a2a/) | `AlgoVoiA2A` + `AlgoVoiPaymentTool` | Yes — `AlgoVoiPaymentTool` callable + full JSON-RPC 2.0 server (`message/send`, `tasks/get`, `tasks/cancel`) + A2A client | **Available** — 84/84 tests, Phase 1 12/12 PASS (16 Apr 2026, Comet-validated) |
| **LangGraph** | [langgraph/](./langgraph/) | `AlgoVoiLangGraph` + `AlgoVoiPaymentTool` | Yes — `BaseTool` subclass, `ToolNode`-compatible, `create_react_agent`-compatible | **Available** — 77/77 tests, Phase 1 12/12 PASS (16 Apr 2026, Comet-validated) |

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

## Quick start (Hugging Face)

```python
from huggingface_algovoi import AlgoVoiHuggingFace

gate = AlgoVoiHuggingFace(
    hf_token          = "hf_...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "meta-llama/Meta-Llama-3-8B-Instruct",
)

# Gate InferenceClient
result = gate.check(headers, body)
if not result.requires_payment:
    reply = gate.complete(body["messages"])

# Gate a transformers pipeline
from transformers import pipeline
pipe = pipeline("text-generation", model="HuggingFaceH4/zephyr-7b-beta", token="hf_...")
if not result.requires_payment:
    answer = gate.inference_pipeline(pipe, body["messages"])

# Drop into a smolagents ToolCallingAgent
from smolagents import ToolCallingAgent, InferenceClientModel
tool  = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")
agent = ToolCallingAgent(tools=[tool], model=InferenceClientModel(...))
agent.run("Use premium_kb to answer my question.")
```

See [huggingface/README.md](./huggingface/README.md) for the full reference.

---

## Quick start (AutoGen)

```python
from autogen_algovoi import AlgoVoiAutoGen

gate = AlgoVoiAutoGen(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "gpt-4o",
)

# Build agents from gate.llm_config
from autogen import AssistantAgent, UserProxyAgent
assistant  = AssistantAgent("assistant",  llm_config=gate.llm_config)
user_proxy = UserProxyAgent("user_proxy", human_input_mode="NEVER",
                             max_consecutive_auto_reply=3,
                             code_execution_config=False)

# Gate a conversation
result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.initiate_chat(assistant, user_proxy, body["message"], max_turns=5)

# Drop a callable tool into agents (0.2.x)
tool = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")

@user_proxy.register_for_execution()
@assistant.register_for_llm(description=tool.description, name=tool.name)
def premium_kb(query: str, payment_proof: str = "") -> str:
    return tool(query=query, payment_proof=payment_proof)

# AutoGen 0.4.x — wrap with FunctionTool
from autogen_core.tools import FunctionTool
fn_tool = FunctionTool(tool, description=tool.description, name=tool.name)
```

See [autogen/README.md](./autogen/README.md) for the full reference.

---

## Quick start (Semantic Kernel)

```python
from semantic_kernel_algovoi import AlgoVoiSemanticKernel

gate = AlgoVoiSemanticKernel(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "gpt-4o",
)

# Gate SK chat completion
result = gate.check(headers, body)
if not result.requires_payment:
    reply = gate.complete(body["messages"])

# Gate any KernelFunction
from semantic_kernel import Kernel
kernel = Kernel()
# ... add services ...
fn     = kernel.plugins["MyPlugin"]["my_function"]
output = gate.invoke_function(kernel, fn, input=body["text"])

# Add as a plugin with @kernel_function
plugin = gate.as_plugin(resource_fn=lambda q: my_handler(q), plugin_name="premium_kb")
kernel.add_plugin(plugin, plugin_name="premium_kb")
```

See [semantic-kernel/README.md](./semantic-kernel/README.md) for the full reference.

---

## Quick start (Pydantic AI)

```python
from pydanticai_algovoi import AlgoVoiPydanticAI

gate = AlgoVoiPydanticAI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "openai:gpt-4o",     # any Pydantic AI provider:model string
)

# Gate chat completion (sync wrapper around async Agent.run())
result = gate.check(headers, body)
if not result.requires_payment:
    reply = gate.complete(body["messages"])

# Gate any pre-built Agent (with optional deps injection)
from pydantic_ai import Agent
my_agent = Agent("anthropic:claude-opus-4-5")
output = gate.run_agent(my_agent, body["prompt"], deps=my_deps)

# Drop into any Agent as a pydantic_ai.tools.Tool
from pydantic_ai.tools import Tool
tool  = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")
agent = Agent("openai:gpt-4o", tools=[Tool(tool, name=tool.name, description=tool.description)])
```

See [pydantic-ai/README.md](./pydantic-ai/README.md) for the full reference.

---

## Quick start (DSPy)

```python
from dspy_algovoi import AlgoVoiDSPy

gate = AlgoVoiDSPy(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,
    model             = "openai/gpt-4o",   # DSPy provider/model string (slash, not colon)
)

# Gate any DSPy module or compiled program
import dspy

class QA(dspy.Signature):
    """Answer the question."""
    question: str = dspy.InputField()
    answer:   str = dspy.OutputField()

result = gate.check(headers, body)
if not result.requires_payment:
    answer = gate.run_module(dspy.ChainOfThought(QA), question=body["question"])

# Drop into a ReAct agent as a plain callable tool
tool  = gate.as_tool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")
react = dspy.ReAct(QA, tools=[tool])
```

See [dspy/README.md](./dspy/README.md) for the full reference.

---

## Quick start (Vercel AI SDK)

```typescript
import { openai } from "@ai-sdk/openai";
import { AlgoVoiVercelAI } from "./vercel_ai_algovoi";

const gate = new AlgoVoiVercelAI({
  algovoiKey:       "algv_...",
  tenantId:         "your-tenant-uuid",
  payoutAddress:    "YOUR_ALGORAND_ADDRESS",
  protocol:         "mpp",
  network:          "algorand-mainnet",
  amountMicrounits: 10_000,
  model:            openai("gpt-4o"),  // any @ai-sdk/* provider
});

// Next.js App Router — one-liner
export const POST = (req: Request) => gate.nextHandler(req);

// Streaming
export async function POST(req: Request) {
  const body = await req.json();
  const result = await gate.check(req.headers, body);
  if (result.requiresPayment) return result.as402Response();
  return gate.streamText(body.messages).toDataStreamResponse();
}

// Payment tool for LLM function calling
const tool = gate.asTool(resource_fn=lambda q: my_handler(q), tool_name="premium_kb")
// Use in generateText({ tools: { premium_kb: tool } })
```

See [vercel-ai-sdk/README.md](./vercel-ai-sdk/README.md) for the full reference.

---

## Quick start (Google A2A)

```python
from a2a_algovoi import AlgoVoiA2A

gate = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    protocol="mpp",
    network="algorand-mainnet",
    amount_microunits=10_000,    # 0.01 USDC per call
    agent_name="My AlgoVoi Agent",
)

# Flask A2A server — one-liner
from flask import Flask, jsonify
app = Flask(__name__)

@app.route("/a2a", methods=["POST"])
def a2a_endpoint():
    return gate.flask_agent(lambda text: my_llm(text))

@app.route("/.well-known/agent-card.json")
def card():
    return jsonify(gate.agent_card("https://myhost.com/a2a"))

# A2A client — call another agent
response = gate.send_message("https://other-agent.example.com/a2a", "What is AlgoVoi?")
# → {"error": {"code": -32000, "message": "payment_required", ...}}  if no proof
# → {"result": {"id": "...", "status": {"state": "completed"}, "artifacts": [...]}}  if paid

# Payment tool for A2A agent pipelines
tool = gate.as_tool(resource_fn=lambda q: my_kb(q), tool_name="premium_kb")
# tool(query="...", payment_proof="")         → challenge JSON
# tool(query="...", payment_proof="<proof>")  → KB result string
```

See [a2a/README.md](./a2a/README.md) for the full reference.

---

## Quick start (LangGraph)

```python
from langgraph_algovoi import AlgoVoiLangGraph

gate = AlgoVoiLangGraph(
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",             # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10000,             # 0.01 USDC per call
)

# Gate a compiled StateGraph
result = gate.check(headers, body)
if not result.requires_payment:
    output = gate.invoke_graph(compiled_graph, {"messages": body["messages"]})

# Streaming
for chunk in gate.stream_graph(compiled_graph, {"messages": [...]},
                               stream_mode="updates"):
    print(chunk)

# Drop into create_react_agent or ToolNode
from langgraph.prebuilt import create_react_agent
tool  = gate.as_tool(resource_fn=lambda q: my_kb(q), tool_name="premium_kb")
agent = create_react_agent(llm, tools=[tool])

# Or use the ready-to-use ToolNode
node = gate.tool_node(resource_fn=lambda q: my_kb(q), tool_name="premium_kb")
graph.add_node("tools", node)
```

See [langgraph/README.md](./langgraph/README.md) for the full reference.

---

Licensed under the [Business Source License 1.1](../LICENSE).
