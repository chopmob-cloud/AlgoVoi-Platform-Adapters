"""
AlgoVoi CrewAI Adapter — Deployment Examples
=============================================
Demonstrates three integration patterns:
  1. Flask server — gate crew.kickoff() behind MPP payment
  2. FastAPI server — gate crew.kickoff() with structured inputs
  3. Standalone AlgoVoiPaymentTool — drop into any CrewAI agent

Run Flask:   python example.py flask
Run FastAPI: uvicorn example:fastapi_app --reload
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ap2-adapter"))

from crewai_algovoi import AlgoVoiCrewAI

# ── Shared gate config ────────────────────────────────────────────────────────

OPENAI_KEY    = os.environ.get("OPENAI_KEY", "sk-...")
ALGOVOI_KEY   = os.environ.get("ALGOVOI_KEY", "algv_...")
TENANT_ID     = os.environ.get("TENANT_ID", "your-tenant-uuid")
PAYOUT_ADDR   = os.environ.get("PAYOUT_ADDRESS", "YOUR_ALGORAND_ADDRESS")

gate = AlgoVoiCrewAI(
    openai_key        = OPENAI_KEY,
    algovoi_key       = ALGOVOI_KEY,
    tenant_id         = TENANT_ID,
    payout_address    = PAYOUT_ADDR,
    protocol          = "mpp",
    network           = "algorand-mainnet",
    amount_microunits = 10000,   # 0.01 USDC per crew run
    model             = "openai/gpt-4o",
)

# ── Example 1: Flask server ───────────────────────────────────────────────────

from flask import Flask, request, jsonify

flask_app = Flask(__name__)


def _build_research_crew(openai_key: str):
    """Build a simple CrewAI research crew (illustrative — adapt to your use case)."""
    from crewai import Agent, Task, Crew, LLM

    llm = LLM(model="openai/gpt-4o", api_key=openai_key)

    researcher = Agent(
        role="Research Analyst",
        goal="Research the given topic thoroughly and produce a concise summary.",
        backstory="Expert researcher with deep knowledge across technology and finance.",
        llm=llm,
        verbose=False,
    )

    task = Task(
        description="Research the topic: {topic}. Produce a 3-paragraph summary.",
        expected_output="A concise 3-paragraph summary of the topic.",
        agent=researcher,
    )

    return Crew(agents=[researcher], tasks=[task], verbose=False)


@flask_app.route("/ai/research", methods=["POST"])
def research():
    """
    Gate a CrewAI research crew behind MPP payment.

    Expects: {"topic": "Algorand blockchain"}
    """
    body   = request.get_json(silent=True) or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        return result.as_flask_response()

    crew = _build_research_crew(OPENAI_KEY)
    output = gate.crew_kickoff(crew, inputs={"topic": body.get("topic", "")})
    return jsonify({"content": output})


@flask_app.route("/ai/research/guard", methods=["POST"])
def research_guard():
    """Convenience one-liner using flask_guard with inputs_fn."""
    crew = _build_research_crew(OPENAI_KEY)
    return gate.flask_guard(crew, inputs_fn=lambda b: {"topic": b.get("topic", "")})


# ── Example 2: FastAPI server ─────────────────────────────────────────────────

try:
    from fastapi import FastAPI
    from fastapi.requests import Request as FastAPIRequest
    from fastapi.responses import JSONResponse, Response as FastAPIResponse

    fastapi_app = FastAPI(title="AlgoVoi CrewAI Gateway")

    @fastapi_app.post("/ai/research")
    async def fastapi_research(req: FastAPIRequest):
        body   = await req.json()
        result = gate.check(dict(req.headers), body)
        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return FastAPIResponse(body_bytes, status_code=402, headers=dict(headers))

        crew   = _build_research_crew(OPENAI_KEY)
        output = gate.crew_kickoff(crew, inputs={"topic": body.get("topic", "")})
        return JSONResponse({"content": output})

except ImportError:
    fastapi_app = None  # FastAPI not installed


# ── Example 3: AlgoVoiPaymentTool in a CrewAI agent ──────────────────────────

def run_agent_example():
    """
    Demonstrates an agent using AlgoVoiPaymentTool to access premium content.

    The agent's LLM generates the payment proof externally; here we simulate
    the two call paths: no proof (challenge) and with proof (resource).
    """
    from crewai import Agent, Task, Crew, LLM
    import json

    # Build the payment-gated tool
    def premium_kb(query: str) -> str:
        return (
            f"[PREMIUM KNOWLEDGE] AlgoVoi settles USDC on-chain in ~4.5 seconds "
            f"on Algorand. Query was: '{query}'"
        )

    payment_tool = gate.as_tool(
        resource_fn      = premium_kb,
        tool_name        = "premium_knowledge_base",
        tool_description = (
            "Query the payment-gated AlgoVoi premium knowledge base. "
            "Provide 'query' with your question and 'payment_proof' (base64-encoded). "
            "Returns a payment challenge if proof is absent or invalid, "
            "or the premium knowledge base answer when payment is verified."
        ),
    )

    print("\n[Tool] Calling _run() without proof (simulating no payment):")
    challenge = payment_tool._run(query="What is AlgoVoi's settlement time?", payment_proof="")
    challenge_data = json.loads(challenge)
    print(f"  Result: {challenge_data}")

    # In a real setup the agent sends a payment and gets a proof.
    # Here we illustrate the verified path with a placeholder:
    print("\n[Tool] Calling _run() with proof (simulating verified payment):")
    simulated_proof = "SIMULATED_BASE64_PROOF_WOULD_GO_HERE"
    # (This would fail gate verification in production — for illustration only)
    print("  (Proof verification would happen against live gateway in production)")

    # Build a CrewAI agent with the tool registered
    llm = LLM(model="openai/gpt-4o", api_key=OPENAI_KEY)

    researcher = Agent(
        role="Blockchain Researcher",
        goal="Use the premium_knowledge_base tool to answer questions about AlgoVoi.",
        backstory="Expert in blockchain technology with access to premium data sources.",
        llm=llm,
        tools=[payment_tool],
        verbose=True,
    )

    task = Task(
        description="Use the premium_knowledge_base tool to find out AlgoVoi's settlement time.",
        expected_output="A factual answer about AlgoVoi's settlement speed.",
        agent=researcher,
    )

    crew = Crew(agents=[researcher], tasks=[task], verbose=True)
    print("\n[Crew] Starting crew.kickoff()...")
    result = gate.crew_kickoff(crew, inputs={})
    print(f"\n[Crew] Result: {result}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "flask"
    if mode == "flask":
        flask_app.run(debug=True, port=5011)
    elif mode == "agent":
        run_agent_example()
    else:
        print("Usage: python example.py [flask|agent]")
