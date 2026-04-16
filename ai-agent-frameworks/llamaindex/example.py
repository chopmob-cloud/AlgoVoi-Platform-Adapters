"""
AlgoVoi LlamaIndex Adapter — Deployment Examples
==================================================
Demonstrates three integration patterns:
  1. Flask server (simple LLM completion gate)
  2. FastAPI server (query engine gate)
  3. ReAct agent with AlgoVoiPaymentTool

Run Flask:   python example.py flask
Run FastAPI: uvicorn example:fastapi_app --reload
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ap2-adapter"))

from llamaindex_algovoi import AlgoVoiLlamaIndex

# ── Shared gate config ────────────────────────────────────────────────────────

OPENAI_KEY    = os.environ.get("OPENAI_KEY", "sk-...")
ALGOVOI_KEY   = os.environ.get("ALGOVOI_KEY", "algv_...")
TENANT_ID     = os.environ.get("TENANT_ID", "your-tenant-uuid")
PAYOUT_ADDR   = os.environ.get("PAYOUT_ADDRESS", "YOUR_ALGORAND_ADDRESS")

gate = AlgoVoiLlamaIndex(
    openai_key        = OPENAI_KEY,
    algovoi_key       = ALGOVOI_KEY,
    tenant_id         = TENANT_ID,
    payout_address    = PAYOUT_ADDR,
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,   # 0.01 USDC per call
    model             = "gpt-4o",
)

# ── Example 1: Flask server ───────────────────────────────────────────────────

from flask import Flask, request, jsonify

flask_app = Flask(__name__)


@flask_app.route("/ai/complete", methods=["POST"])
def complete():
    """Simple LLM completion gate — OpenAI-format message list."""
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()
    return jsonify({"content": gate.complete(body.get("messages", []))})


@flask_app.route("/ai/query", methods=["POST"])
def query():
    """
    RAG query engine gate.

    Expects: {"query": "What is AlgoVoi?"}
    Builds a simple in-memory LlamaIndex index over a local docs/ directory.
    """
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()

    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    if not os.path.isdir(docs_dir):
        return jsonify({"error": "docs/ directory not found — add some .txt files to gate"}), 500

    documents    = SimpleDirectoryReader(docs_dir).load_data()
    index        = VectorStoreIndex.from_documents(documents)
    query_engine = index.as_query_engine()

    answer = gate.query_engine_query(query_engine, body.get("query", ""))
    return jsonify({"content": answer})


@flask_app.route("/ai/chat", methods=["POST"])
def chat():
    """
    Chat engine gate — multi-turn conversation.

    Expects: {"message": "Tell me more about AlgoVoi"}
    """
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()

    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    if os.path.isdir(docs_dir):
        documents    = SimpleDirectoryReader(docs_dir).load_data()
        index        = VectorStoreIndex.from_documents(documents)
        chat_engine  = index.as_chat_engine(chat_mode="best")
        reply        = gate.chat_engine_chat(chat_engine, body.get("message", ""))
    else:
        # Fall back to plain LLM if no docs
        reply = gate.complete([{"role": "user", "content": body.get("message", "")}])

    return jsonify({"content": reply})


@flask_app.route("/ai/guard", methods=["POST"])
def guard():
    """Convenience one-liner: check + complete in a single call."""
    return gate.flask_guard()


# ── Example 2: FastAPI server ─────────────────────────────────────────────────

try:
    from fastapi import FastAPI
    from fastapi.requests import Request as FastAPIRequest
    from fastapi.responses import JSONResponse, Response as FastAPIResponse

    fastapi_app = FastAPI(title="AlgoVoi LlamaIndex Gateway")

    @fastapi_app.post("/ai/complete")
    async def fastapi_complete(req: FastAPIRequest):
        body   = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return FastAPIResponse(body_bytes, status_code=402, headers=dict(headers))
        return JSONResponse({"content": gate.complete(body.get("messages", []))})

    @fastapi_app.post("/ai/query")
    async def fastapi_query(req: FastAPIRequest):
        from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

        body   = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return FastAPIResponse(body_bytes, status_code=402, headers=dict(headers))

        docs_dir = os.path.join(os.path.dirname(__file__), "docs")
        if not os.path.isdir(docs_dir):
            return JSONResponse({"error": "docs/ directory not found"}, status_code=500)

        documents    = SimpleDirectoryReader(docs_dir).load_data()
        index        = VectorStoreIndex.from_documents(documents)
        query_engine = index.as_query_engine()
        answer       = gate.query_engine_query(query_engine, body.get("query", ""))
        return JSONResponse({"content": answer})

except ImportError:
    fastapi_app = None  # FastAPI not installed


# ── Example 3: ReAct agent with AlgoVoiPaymentTool ───────────────────────────

def run_agent_example():
    """
    Demonstrates dropping AlgoVoiPaymentTool into a LlamaIndex ReAct agent.

    The agent can decide to pay for premium content as part of its reasoning loop.
    """
    from llama_index.core.agent import ReActAgent
    from llama_index.llms.openai import OpenAI as LlamaOpenAI

    # Premium resource the tool protects
    def premium_knowledge_base(query: str) -> str:
        return f"[PREMIUM] Detailed answer to '{query}': AlgoVoi settles USDC on-chain in ~5s."

    # Build the payment-gated tool
    payment_tool = gate.as_tool(
        resource_fn      = premium_knowledge_base,
        tool_name        = "premium_kb",
        tool_description = (
            "Query the payment-gated AlgoVoi knowledge base. "
            'Input JSON: {"query": "<question>", "payment_proof": "<base64>"}. '
            "Returns challenge JSON if proof is absent, or the knowledge base answer if verified."
        ),
    )

    # Build a ReAct agent with the payment tool
    llm   = LlamaOpenAI(model="gpt-4o", api_key=OPENAI_KEY)
    agent = ReActAgent.from_tools([payment_tool], llm=llm, verbose=True)

    print("\n[Agent] Asking question without payment proof...")
    response = agent.chat(
        "Use the premium_kb tool to answer: What is AlgoVoi's settlement time?"
    )
    print(f"[Agent] Response: {response}")


# ── Custom ChatModel (bring your own model) ───────────────────────────────────

def run_anthropic_example():
    """
    Use a pre-built LangChain ChatAnthropic as the LLM — no OpenAI key required.
    """
    from langchain_anthropic import ChatAnthropic

    anthropic_gate = AlgoVoiLlamaIndex(
        algovoi_key       = ALGOVOI_KEY,
        tenant_id         = TENANT_ID,
        payout_address    = PAYOUT_ADDR,
        llm               = ChatAnthropic(model="claude-opus-4-5"),
        protocol          = "mpp",
        network           = "algorand-mainnet",
        amount_microunits = 10000,
    )
    print("[Custom model] Gate built with ChatAnthropic:", anthropic_gate)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "flask"
    if mode == "flask":
        flask_app.run(debug=True, port=5010)
    elif mode == "agent":
        run_agent_example()
    else:
        print("Usage: python example.py [flask|agent]")
