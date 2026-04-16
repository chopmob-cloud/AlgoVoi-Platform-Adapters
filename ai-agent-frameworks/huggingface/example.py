"""
AlgoVoi Hugging Face Adapter — usage examples
===============================================

Requires:
    pip install huggingface-hub transformers smolagents flask fastapi uvicorn
"""

# ── 1. Flask — gate InferenceClient.chat_completion() ─────────────────────────

from flask import Flask, request, jsonify
from huggingface_algovoi import AlgoVoiHuggingFace

app = Flask(__name__)

gate = AlgoVoiHuggingFace(
    hf_token          = "hf_...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "mpp",               # "mpp" | "ap2" | "x402"
    network           = "algorand-mainnet",  # see NETWORKS
    amount_microunits = 10_000,              # 0.01 USDC per call
    model             = "meta-llama/Meta-Llama-3-8B-Instruct",
)

# Option A — manual check + complete
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


# ── 3. transformers pipeline ───────────────────────────────────────────────────

from transformers import pipeline  # type: ignore

pipe = pipeline(
    "text-generation",
    model="HuggingFaceH4/zephyr-7b-beta",
    token="hf_...",
)

@app.route("/ai/generate", methods=["POST"])
def generate():
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    answer = gate.inference_pipeline(pipe, body.get("messages", []))
    return jsonify({"content": answer})


# ── 4. smolagents tool ─────────────────────────────────────────────────────────

def premium_knowledge_base(query: str) -> str:
    """Simulate a protected resource — replace with your actual handler."""
    return f"Premium answer for: {query}"

tool = gate.as_tool(
    resource_fn      = premium_knowledge_base,
    tool_name        = "premium_kb",
    tool_description = "Query the payment-gated knowledge base. "
                       "Provide query and payment_proof.",
)

# Drop into a smolagents ToolCallingAgent:
try:
    from smolagents import ToolCallingAgent, InferenceClientModel  # type: ignore

    model  = InferenceClientModel(model_id="meta-llama/Meta-Llama-3-8B-Instruct")
    agent  = ToolCallingAgent(tools=[tool], model=model)
    answer = agent.run(
        "Access the premium knowledge base to answer: What is AlgoVoi?"
    )
    print(answer)
except ImportError:
    print("smolagents not installed — skipping agent example")


# ── 5. Bring your own model / endpoint ────────────────────────────────────────

# Dedicated Inference Endpoint (any HF-hosted model)
custom_gate = AlgoVoiHuggingFace(
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ADDRESS",
    hf_token          = "hf_...",
    base_url          = "https://your-endpoint.endpoints.huggingface.cloud",
    model             = "meta-llama/Meta-Llama-3-8B-Instruct",
    protocol          = "ap2",
    network           = "voi-mainnet",
    amount_microunits = 5_000,  # 0.005 USDC
)

# ── 6. Bring your own gate protocol ───────────────────────────────────────────

x402_gate = AlgoVoiHuggingFace(
    hf_token          = "hf_...",
    algovoi_key       = "algv_...",
    tenant_id         = "your-tenant-uuid",
    payout_address    = "YOUR_ALGORAND_ADDRESS",
    protocol          = "x402",
    network           = "stellar-mainnet",
    amount_microunits = 10_000,
)
