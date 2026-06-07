"""
DSPy adapter usage examples
============================

This file shows common patterns for gating DSPy programs and modules
behind AlgoVoi payment verification.

Run locally:
    pip install dspy flask
    ALGOVOI_KEY=algv_... TENANT_ID=... PAYOUT_ADDRESS=... \
        python example.py
"""

from __future__ import annotations

# ── 1. Flask endpoint — gate a DSPy Predict call ──────────────────────────────

from flask import Flask, request, jsonify
from dspy_algovoi import AlgoVoiDSPy

app = Flask(__name__)

gate = AlgoVoiDSPy(
    algovoi_key="algv_your_key",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    openai_key="sk-...",          # or omit to use OPENAI_API_KEY env var
    protocol="mpp",               # "mpp" | "ap2" | "x402"
    network="algorand-mainnet",   # or "voi-mainnet" / "hedera-mainnet" / "stellar-mainnet"
    amount_microunits=10_000,     # 0.01 USDC per call
    model="openai/gpt-4o",        # DSPy provider/model string
)


@app.route("/ai/chat", methods=["POST"])
def chat():
    result = gate.check(dict(request.headers), request.get_json(silent=True) or {})
    if result.requires_payment:
        return result.as_flask_response()

    messages = request.json.get("messages", [])
    content = gate.complete(messages)
    return jsonify({"content": content})


# ── 2. One-liner Flask guard ──────────────────────────────────────────────────

@app.route("/ai/v2/chat", methods=["POST"])
def chat_guard():
    return gate.flask_guard()


# ── 3. Gate a pre-built DSPy module (Predict / ChainOfThought / ReAct) ────────

import dspy


class QASignature(dspy.Signature):
    """Answer the question as accurately as possible."""
    question: str = dspy.InputField(desc="The question to answer")
    answer: str = dspy.OutputField(desc="A concise answer")


qa_module = dspy.Predict(QASignature)


@app.route("/ai/qa", methods=["POST"])
def qa():
    data = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), data)
    if result.requires_payment:
        return result.as_flask_response()

    question = data.get("question", "")
    answer = gate.run_module(qa_module, question=question)
    return jsonify({"answer": answer})


# ── 4. Gate a ChainOfThought module ──────────────────────────────────────────

class MathSignature(dspy.Signature):
    """Solve the math problem step by step."""
    problem: str = dspy.InputField(desc="A math problem")
    solution: str = dspy.OutputField(desc="Step-by-step solution")


cot_module = dspy.ChainOfThought(MathSignature)


@app.route("/ai/math", methods=["POST"])
def math():
    data = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), data)
    if result.requires_payment:
        return result.as_flask_response()

    problem = data.get("problem", "")
    solution = gate.run_module(cot_module, problem=problem)
    return jsonify({"solution": solution})


# ── 5. ReAct agent with AlgoVoi payment tool ─────────────────────────────────

def premium_knowledge_base(query: str) -> str:
    """Return premium content for the given query."""
    # In production this would query a database, vector store, etc.
    return f"Premium answer to: {query}"


payment_tool = gate.as_tool(
    resource_fn=premium_knowledge_base,
    tool_name="premium_kb",
    tool_description=(
        "Access premium knowledge base. "
        "Provide query (the question) and payment_proof "
        "(base64-encoded payment proof — empty string to receive a challenge)."
    ),
)


class AgentQA(dspy.Signature):
    """Answer the user question, using the premium_kb tool if needed."""
    question: str = dspy.InputField()
    answer: str = dspy.OutputField()


react_agent = dspy.ReAct(AgentQA, tools=[payment_tool])


@app.route("/ai/agent", methods=["POST"])
def agent_endpoint():
    data = request.get_json(silent=True) or {}
    # The ReAct agent handles payment internally via the tool
    question = data.get("question", "")
    lm = gate._ensure_lm()
    with dspy.context(lm=lm):
        result = react_agent(question=question)
    return jsonify({"answer": result.answer})


# ── 6. WSGI middleware — gate every request before routing ───────────────────

class AlgoVoiWsgiMiddleware:
    def __init__(self, wsgi_app, gate: AlgoVoiDSPy):
        self.app = wsgi_app
        self.gate = gate

    def __call__(self, environ, start_response):
        from wsgiref.headers import Headers

        # Convert WSGI environ to a headers dict
        headers = {
            k[5:].replace("_", "-").title(): v
            for k, v in environ.items()
            if k.startswith("HTTP_")
        }
        result = self.gate.check(headers, {})
        if result.requires_payment:
            status, resp_headers, body = result.as_wsgi_response()
            start_response(f"{status} Payment Required", resp_headers)
            return [body]
        return self.app(environ, start_response)


# app.wsgi_app = AlgoVoiWsgiMiddleware(app.wsgi_app, gate)


# ── 7. Anthropic model (Claude) ───────────────────────────────────────────────

gate_claude = AlgoVoiDSPy(
    algovoi_key="algv_your_key",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    protocol="ap2",
    network="stellar-mainnet",
    model="anthropic/claude-opus-4-5",   # DSPy Anthropic provider
    # DSPy picks up ANTHROPIC_API_KEY from env
)


# ── 8. Ollama (local model, no payment key needed for LLM calls) ──────────────

gate_ollama = AlgoVoiDSPy(
    algovoi_key="algv_your_key",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    protocol="mpp",
    network="algorand-mainnet",
    model="ollama_chat/llama3",       # Ollama provider
    base_url="http://localhost:11434", # DSPy uses api_base
)


# ── 9. Hedera + x402 ─────────────────────────────────────────────────────────

gate_hedera = AlgoVoiDSPy(
    algovoi_key="algv_your_key",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_HEDERA_ADDRESS",
    protocol="x402",
    network="hedera-mainnet",
    amount_microunits=5_000,           # 0.005 USDC
    model="openai/gpt-4o-mini",
)


if __name__ == "__main__":
    app.run(debug=True)
