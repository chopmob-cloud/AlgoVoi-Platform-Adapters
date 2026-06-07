"""
AlgoVoi AutoGen Adapter — usage examples
=========================================

Requires:
    pip install pyautogen flask fastapi uvicorn
"""

from flask import Flask, request, jsonify
from autogen_algovoi import AlgoVoiAutoGen

app = Flask(__name__)

gate = AlgoVoiAutoGen(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",               # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10_000,              # 0.01 USDC per conversation
    model             = "gpt-4o",
)

# ── 1. Build AutoGen agents using gate.llm_config ─────────────────────────────
try:
    from autogen import AssistantAgent, UserProxyAgent  # type: ignore

    assistant = AssistantAgent(
        name       = "assistant",
        llm_config = gate.llm_config,  # {"config_list": [{"model": "gpt-4o", "api_key": "sk-..."}]}
    )

    user_proxy = UserProxyAgent(
        name             = "user_proxy",
        human_input_mode = "NEVER",
        max_consecutive_auto_reply = 3,
        code_execution_config      = False,
    )
except ImportError:
    print("pyautogen not installed — skipping agent setup")
    assistant = None
    user_proxy = None


# ── 2. Flask — gate initiate_chat() ──────────────────────────────────────────

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
        max_turns = body.get("max_turns", 5),
    )
    return jsonify({"content": output})


# Option B — convenience one-liner with message extractor
@app.route("/ai/chat-easy", methods=["POST"])
def chat_easy():
    return gate.flask_guard(
        sender      = user_proxy,
        recipient   = assistant,
        message_fn  = lambda b: b.get("message", ""),
        max_turns   = 5,
    )


# ── 3. FastAPI ─────────────────────────────────────────────────────────────────

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
    output = gate.initiate_chat(
        recipient = assistant,
        sender    = user_proxy,
        message   = body.get("message", ""),
        max_turns = 5,
    )
    return JSONResponse({"content": output})


# ── 4. AutoGen 0.2.x callable tool ────────────────────────────────────────────

def premium_knowledge_base(query: str) -> str:
    """Simulate a protected resource — replace with your actual handler."""
    return f"Premium answer for: {query}"

tool = gate.as_tool(
    resource_fn      = premium_knowledge_base,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base. "
                       "Provide query and payment_proof (base64).",
)

# Register with AutoGen 0.2.x agents:
try:
    @user_proxy.register_for_execution()  # type: ignore
    @assistant.register_for_llm(description=tool.description, name=tool.name)  # type: ignore
    def premium_kb(query: str, payment_proof: str = "") -> str:
        return tool(query=query, payment_proof=payment_proof)
except (AttributeError, TypeError):
    pass


# ── 5. AutoGen 0.4.x FunctionTool ─────────────────────────────────────────────

try:
    from autogen_core.tools import FunctionTool  # type: ignore
    from autogen_agentchat.agents import AssistantAgent as AssistantAgent04  # type: ignore
    from autogen_ext.models.openai import OpenAIChatCompletionClient  # type: ignore

    fn_tool   = FunctionTool(tool, description=tool.description, name=tool.name)
    model_04  = OpenAIChatCompletionClient(model="gpt-4o", api_key="sk-...")
    agent_04  = AssistantAgent04("assistant", tools=[fn_tool], model_client=model_04)
except ImportError:
    print("autogen_agentchat not installed — skipping 0.4.x example")


# ── 6. GroupChat with payment-gated tools ─────────────────────────────────────

try:
    from autogen import GroupChat, GroupChatManager  # type: ignore

    group = GroupChat(agents=[assistant, user_proxy], messages=[], max_round=6)
    manager = GroupChatManager(groupchat=group, llm_config=gate.llm_config)

    @app.route("/ai/group", methods=["POST"])
    def group_chat():
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()
        output = gate.initiate_chat(
            recipient = manager,
            sender    = user_proxy,
            message   = body.get("message", ""),
            max_turns = 6,
        )
        return jsonify({"content": output})
except ImportError:
    pass


# ── 7. Bring your own LLM config ──────────────────────────────────────────────

# Use any OpenAI-compatible provider via base_url:
azure_gate = AlgoVoiAutoGen(
    algovoi_key       = "algv_...",
    tenant_id         = "...",
    payout_address    = "...",
    openai_key        = "AZURE_API_KEY",
    model             = "gpt-4o",
    base_url          = "https://YOUR_RESOURCE.openai.azure.com/",
    protocol          = "ap2",
    network           = "voi-mainnet",
    amount_microunits = 5_000,
)
