"""
AlgoVoi Pydantic AI Adapter -- usage examples
===============================================

Requires:
    pip install pydantic-ai flask fastapi uvicorn openai
"""

from flask import Flask, request, jsonify
from pydanticai_algovoi import AlgoVoiPydanticAI

app = Flask(__name__)

gate = AlgoVoiPydanticAI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",               # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10_000,              # 0.01 USDC per call
    model             = "openai:gpt-4o",     # any Pydantic AI provider:model string
    resource_id       = "ai-function",
)


# ── 1. Flask -- gate chat completion ──────────────────────────────────────────

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})


# Option B -- convenience one-liner
@app.route("/ai/chat-easy", methods=["POST"])
def chat_easy():
    return gate.flask_guard()


# ── 2. FastAPI ─────────────────────────────────────────────────────────────────

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

fapi = FastAPI()

@fapi.post("/ai/chat")
async def fastapi_chat(req: Request):
    body   = await req.json()
    result = gate.check(dict(req.headers), body)
    if result.requires_payment:
        status, headers, body_bytes = result.as_wsgi_response()
        return Response(body_bytes, status_code=402, headers=dict(headers))
    # Use async path directly in FastAPI
    reply = await gate._complete_async(body["messages"])
    return JSONResponse({"content": reply})


# ── 3. Gate any pre-built Pydantic AI Agent ───────────────────────────────────

try:
    from pydantic_ai import Agent  # type: ignore
    from pydantic_ai.models.openai import OpenAIModel  # type: ignore
    from openai import AsyncOpenAI  # type: ignore

    # Build your own agent (any provider, any model)
    openai_client = AsyncOpenAI(api_key="sk-...")
    custom_model  = OpenAIModel("gpt-4o", openai_client=openai_client)

    my_agent = Agent(
        custom_model,
        system_prompt="You are a concise assistant. Answer in one sentence.",
    )

    @app.route("/ai/agent", methods=["POST"])
    def agent_endpoint():
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()
        # Gate the pre-built agent with run_agent()
        output = gate.run_agent(my_agent, body.get("prompt", ""))
        return jsonify({"content": output})

except ImportError:
    print("pydantic-ai not installed -- skipping Agent example")


# ── 4. Dependency injection (typed deps) ─────────────────────────────────────

try:
    from pydantic_ai import Agent, RunContext  # type: ignore
    from dataclasses import dataclass

    @dataclass
    class UserDeps:
        user_id: str
        tier: str

    # Agent with deps_type for access control
    premium_agent = Agent(
        "openai:gpt-4o",
        deps_type=UserDeps,
        system_prompt="You are a premium assistant.",
    )

    @app.route("/ai/premium", methods=["POST"])
    def premium_endpoint():
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()
        deps   = UserDeps(user_id=body.get("user_id", "anon"), tier="premium")
        output = gate.run_agent(premium_agent, body.get("prompt", ""), deps=deps)
        return jsonify({"content": output})

except ImportError:
    pass


# ── 5. Payment tool in an Agent ───────────────────────────────────────────────

def premium_knowledge_base(query: str) -> str:
    """Simulate a protected resource -- replace with your actual handler."""
    return f"Premium answer for: {query}"

tool = gate.as_tool(
    resource_fn      = premium_knowledge_base,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base. "
                       "Provide query and payment_proof (base64).",
)

try:
    from pydantic_ai import Agent  # type: ignore
    from pydantic_ai.tools import Tool  # type: ignore

    # Wrap the AlgoVoiPaymentTool with pydantic_ai.tools.Tool
    pydantic_tool = Tool(tool, name=tool.name, description=tool.description)

    kb_agent = Agent("openai:gpt-4o", tools=[pydantic_tool])

    # The LLM can select premium_kb automatically when it needs information
    # result = kb_agent.run_sync("What does AlgoVoi charge for transactions?")
    # print(result.data)

except ImportError:
    pass


# ── 6. Bring your own provider / model ───────────────────────────────────────

# Anthropic Claude via Pydantic AI
claude_gate = AlgoVoiPydanticAI(
    algovoi_key       = "algv_...",
    tenant_id         = "...",
    payout_address    = "...",
    protocol          = "ap2",
    network           = "voi-mainnet",
    model             = "anthropic:claude-opus-4-5",
    amount_microunits = 5_000,
)

# Groq (fast inference) via OpenAI-compatible base URL
groq_gate = AlgoVoiPydanticAI(
    openai_key        = "gsk_...",
    algovoi_key       = "algv_...",
    tenant_id         = "...",
    payout_address    = "...",
    protocol          = "mpp",
    network           = "algorand-mainnet",
    model             = "openai:llama-3.3-70b-versatile",
    base_url          = "https://api.groq.com/openai/v1",
    amount_microunits = 1_000,
)

# Ollama (local, self-hosted)
ollama_gate = AlgoVoiPydanticAI(
    algovoi_key       = "algv_...",
    tenant_id         = "...",
    payout_address    = "...",
    protocol          = "x402",
    network           = "algorand-mainnet",
    model             = "openai:llama3.2",
    base_url          = "http://localhost:11434/v1",
    openai_key        = "ollama",  # placeholder; Ollama ignores the key
)
