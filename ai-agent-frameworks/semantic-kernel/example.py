"""
AlgoVoi Semantic Kernel Adapter — usage examples
==================================================

Requires:
    pip install semantic-kernel flask fastapi uvicorn
"""

from flask import Flask, request, jsonify
from semantic_kernel_algovoi import AlgoVoiSemanticKernel

app = Flask(__name__)

gate = AlgoVoiSemanticKernel(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",               # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",
    amount_microunits = 10_000,              # 0.01 USDC per call
    model             = "gpt-4o",
    resource_id       = "ai-function",
)


# ── 1. Flask — gate chat completion ───────────────────────────────────────────

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body["messages"])})


# Option B — convenience one-liner
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
    return JSONResponse({"content": gate.complete(body["messages"])})


# ── 3. Gate any KernelFunction ─────────────────────────────────────────────────

try:
    from semantic_kernel import Kernel  # type: ignore
    from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion  # type: ignore
    from semantic_kernel.prompt_template import PromptTemplateConfig  # type: ignore

    kernel = Kernel()
    kernel.add_service(OpenAIChatCompletion(
        service_id   = "chat",
        ai_model_id  = "gpt-4o",
        api_key      = "sk-...",
    ))

    summarise_fn = kernel.add_function(
        plugin_name  = "utils",
        function_name = "summarise",
        prompt       = "Summarise the following text in one sentence: {{$input}}",
    )

    @app.route("/ai/summarise", methods=["POST"])
    def summarise():
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)
        if result.requires_payment:
            return result.as_flask_response()
        output = gate.invoke_function(kernel, summarise_fn, input=body.get("text", ""))
        return jsonify({"content": output})

except ImportError:
    print("semantic-kernel not installed — skipping KernelFunction example")


# ── 4. Plugin (add to any Kernel) ─────────────────────────────────────────────

def premium_knowledge_base(query: str) -> str:
    """Simulate a protected resource — replace with your actual handler."""
    return f"Premium answer for: {query}"

plugin = gate.as_plugin(
    resource_fn      = premium_knowledge_base,
    plugin_name      = "premium_kb",
    gate_description = "Query the payment-gated knowledge base. "
                       "Provide query and payment_proof (base64).",
)

try:
    from semantic_kernel import Kernel  # type: ignore

    kernel = Kernel()
    kernel.add_plugin(plugin, plugin_name="premium_kb")

    # Invoke the gate function directly:
    # gate_fn = kernel.plugins["premium_kb"]["gate"]
    # output  = gate.invoke_function(kernel, gate_fn, query="...", payment_proof="proof")

    # Or the LLM selects it via function calling (auto-invocation):
    # from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
    # settings = OpenAIChatPromptExecutionSettings(
    #     service_id      = "chat",
    #     auto_invoke_kernel_functions = True,
    #     function_choice_behavior     = "auto",
    # )
except ImportError:
    pass


# ── 5. Bring your own endpoint / model ────────────────────────────────────────

# Azure OpenAI
azure_gate = AlgoVoiSemanticKernel(
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
