"""
AlgoVoi Agno Adapter — Usage Examples
=======================================

Pattern 1:  Explicit check → agent.run()
Pattern 2:  run_agent() wrapper (combined check + run)
Pattern 3:  make_pre_hook() — inject payment gate as an Agno pre-hook
Pattern 4:  fastapi_middleware() — gate all AgentOS routes via ASGI middleware
Pattern 5:  flask_guard() / flask_agent() — Flask integration

Install dependencies:
    pip install agno flask fastapi uvicorn
    pip install openai          # for OpenAIChat model (Pattern 1–5)

Environment variables:
    ALGOVOI_KEY        AlgoVoi API key (algv_...)
    ALGOVOI_TENANT_ID  AlgoVoi tenant ID
    PAYOUT_ADDRESS     Your blockchain wallet address
    OPENAI_API_KEY     OpenAI API key (for examples using GPT-4o)
"""

import os

ALGOVOI_KEY    = os.environ.get("ALGOVOI_KEY", "algv_example")
TENANT_ID      = os.environ.get("ALGOVOI_TENANT_ID", "tenant-example")
PAYOUT_ADDRESS = os.environ.get("PAYOUT_ADDRESS", "ALGO_ADDRESS_HERE")

from agno_algovoi import AlgoVoiAgno

gate = AlgoVoiAgno(
    algovoi_key=ALGOVOI_KEY,
    tenant_id=TENANT_ID,
    payout_address=PAYOUT_ADDRESS,
    protocol="mpp",                 # or "x402" / "ap2"
    network="algorand-mainnet",     # or "voi-mainnet" / "hedera-mainnet" / "stellar-mainnet"
    amount_microunits=10_000,       # $0.01 USDC
    resource_id="ai-assistant",
)


# ─── Pattern 1: Explicit check then agent.run() ───────────────────────────────
# Use when you need full control over what happens between check and run.

def example_pattern1_flask():
    """Flask route with explicit payment check."""
    from flask import Flask, jsonify, request
    from agno.agent import Agent
    from agno.models.openai import OpenAIChat

    app   = Flask(__name__)
    agent = Agent(model=OpenAIChat(id="gpt-4o"), markdown=False)

    @app.route("/ask", methods=["POST"])
    def ask():
        result = gate.check(dict(request.headers), request.get_json())
        if result.requires_payment:
            return result.as_flask_response()    # 402 + payment challenge

        body   = request.get_json()
        output = agent.run(body.get("message", ""))
        return jsonify({"response": output.content})

    return app


# ─── Pattern 2: run_agent() wrapper ──────────────────────────────────────────
# Simplest surface — raises AgnoPaymentRequired if no valid proof.

def example_pattern2_flask():
    """Flask route using run_agent() combined wrapper."""
    from flask import Flask, jsonify, request
    from agno.agent import Agent
    from agno.models.openai import OpenAIChat
    from agno_algovoi import AgnoPaymentRequired

    app   = Flask(__name__)
    agent = Agent(model=OpenAIChat(id="gpt-4o"))

    @app.route("/ask", methods=["POST"])
    def ask():
        body = request.get_json() or {}
        try:
            output = gate.run_agent(
                agent,
                body.get("message", ""),
                headers=dict(request.headers),
                body=body,
            )
            return jsonify({"response": output.content})
        except AgnoPaymentRequired as exc:
            return exc.result.as_flask_response()   # 402

    return app


# ─── Pattern 2b: flask_agent() convenience helper ────────────────────────────

def example_pattern2b_flask():
    """Single-line Flask endpoint using flask_agent()."""
    from flask import Flask
    from agno.agent import Agent
    from agno.models.openai import OpenAIChat

    app   = Flask(__name__)
    agent = Agent(model=OpenAIChat(id="gpt-4o"))

    @app.route("/ask", methods=["POST"])
    def ask():
        return gate.flask_agent(agent, message_key="message")

    return app


# ─── Pattern 3: make_pre_hook() — Agno native hook system ────────────────────
# Lets you construct a gated Agent that enforces payment in the hook lifecycle.

def example_pattern3_pre_hook():
    """
    Build a gated Agent using Agno's pre_hooks mechanism.

    The hook captures the headers at request time and raises
    AgnoPaymentRequired inside the hook before the model is called.
    """
    from flask import Flask, jsonify, request
    from agno.agent import Agent
    from agno.models.openai import OpenAIChat
    from agno_algovoi import AgnoPaymentRequired

    app = Flask(__name__)

    @app.route("/ask", methods=["POST"])
    def ask():
        body = request.get_json() or {}

        # Capture headers at request time, build hook
        hook = gate.make_pre_hook(headers=dict(request.headers), body=body)

        # Inject hook into agent (per-request agent creation keeps hooks stateless)
        agent = Agent(
            model=OpenAIChat(id="gpt-4o"),
            pre_hooks=[hook],
        )

        try:
            output = agent.run(body.get("message", ""))
            return jsonify({"response": output.content})
        except AgnoPaymentRequired as exc:
            return exc.result.as_flask_response()

    return app


# ─── Pattern 4: fastapi_middleware() — AgentOS ASGI middleware ────────────────
# Gates every route on an AgentOS-managed FastAPI app.

def example_pattern4_fastapi():
    """
    Add AlgoVoi payment gate as ASGI middleware to an AgentOS FastAPI app.

    Every HTTP request to any route will be gated — including the built-in
    /agents/{agent_id}/runs endpoints that AgentOS provides.
    """
    from agno.agent import Agent
    from agno.models.openai import OpenAIChat
    from agno.os import AgentOS

    agent    = Agent(model=OpenAIChat(id="gpt-4o"), name="assistant")
    agent_os = AgentOS(agents=[agent])
    app      = agent_os.get_app()

    gate.fastapi_middleware(app)   # add payment gate to all routes

    # Run with: uvicorn example:app --reload
    return app


# ─── Pattern 5: Async FastAPI without AgentOS ────────────────────────────────

def example_pattern5_fastapi_manual():
    """FastAPI endpoint using arun_agent() for async execution."""
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from agno.agent import Agent
    from agno.models.openai import OpenAIChat
    from agno_algovoi import AgnoPaymentRequired

    app   = FastAPI()
    agent = Agent(model=OpenAIChat(id="gpt-4o"))

    @app.post("/ask")
    async def ask(request: Request):
        body    = await request.json()
        headers = dict(request.headers)
        try:
            output = await gate.arun_agent(
                agent,
                body.get("message", ""),
                headers=headers,
                body=body,
            )
            return JSONResponse({"response": output.content})
        except AgnoPaymentRequired as exc:
            status, resp_headers, body_bytes = exc.result.as_wsgi_response()
            return JSONResponse(
                content={"error": "payment_required"},
                status_code=402,
                headers=dict(resp_headers),
            )

    return app


# ─── Run Pattern 2b by default ────────────────────────────────────────────────

if __name__ == "__main__":
    app = example_pattern2b_flask()
    print("Starting Flask server on http://127.0.0.1:5000")
    print("POST /ask  {\"message\": \"What is the capital of France?\"}")
    print("Include Authorization: Payment <proof> for verified access.")
    app.run(debug=True)
