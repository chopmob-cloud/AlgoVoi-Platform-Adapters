"""
AlgoVoi Google A2A Adapter — usage examples
============================================

Demonstrates:
  1. Minimal Flask A2A server endpoint
  2. Agent card endpoint
  3. Manual check + handle_request pattern
  4. A2A client: calling another agent with payment proof
  5. Payment tool inside an A2A agent pipeline
  6. Multi-protocol setup (MPP / AP2 / x402)
  7. Multi-network examples
"""

from a2a_algovoi import AlgoVoiA2A

# ── 1. Minimal Flask A2A server ───────────────────────────────────────────────

from flask import Flask, jsonify, request as flask_request

gate = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    protocol="mpp",
    network="algorand-mainnet",
    amount_microunits=10_000,       # 0.01 USDC per call
    agent_name="My AlgoVoi Agent",
    agent_description="A payment-gated AI assistant.",
)

app = Flask(__name__)


@app.route("/a2a", methods=["POST"])
def a2a_endpoint():
    # One-liner: payment check + JSON-RPC routing
    return gate.flask_agent(lambda text: my_llm(text))


@app.route("/.well-known/agent-card.json")
def agent_card():
    card = gate.agent_card(
        agent_url="https://myhost.example.com/a2a",
        skills=[
            {
                "id":          "premium-qa",
                "name":        "Premium Q&A",
                "description": "Answer questions from the private knowledge base.",
            }
        ],
        supports_streaming=False,
    )
    return jsonify(card)


def my_llm(text: str) -> str:
    # Replace with your actual LLM call
    return f"Echo: {text}"


# ── 2. Manual check + handle_request ─────────────────────────────────────────

@app.route("/a2a/manual", methods=["POST"])
def a2a_manual():
    """Explicit control flow for logging / custom error handling."""
    guard = gate.flask_guard()
    if guard is not None:
        return guard  # 402 with challenge header

    body = flask_request.get_json(force=True) or {}
    response = gate.handle_request(body, my_llm)
    return jsonify(response)


# ── 3. A2A client — call another agent ───────────────────────────────────────

def call_remote_agent(agent_url: str, question: str, payment_proof: str = "") -> dict:
    """
    Call a remote A2A agent.

    If no proof is given, the response will contain a 402 challenge in
    response.error.data.challenge_headers. Pay on-chain, then retry with proof.
    """
    return gate.send_message(
        agent_url=agent_url,
        text=question,
        payment_proof=payment_proof,
        timeout=30,
    )


# First call → 402 challenge
response = call_remote_agent("https://other-agent.example.com/a2a", "What is AlgoVoi?")
if response.get("error", {}).get("message") == "payment_required":
    challenge_headers = response["error"]["data"]["challenge_headers"]
    print("Payment required. Challenge:", challenge_headers)

    # ... user pays on-chain, gets proof ...
    # proof = "base64-proof-from-blockchain"

    # Second call with proof
    # response = call_remote_agent(
    #     "https://other-agent.example.com/a2a",
    #     "What is AlgoVoi?",
    #     payment_proof=proof,
    # )
    # task = response["result"]
    # print(task["artifacts"][0]["parts"][0]["text"])


# ── 4. Payment tool inside an A2A agent pipeline ──────────────────────────────

def build_agent_with_payment_tool():
    """
    Create a payment-gated tool and use it inside an A2A message handler.

    The LLM can decide when to call the premium tool by including paymentProof
    in the user message or retrieving it from an on-chain transaction.
    """
    kb_tool = gate.as_tool(
        resource_fn=lambda query: fetch_from_knowledge_base(query),
        tool_name="premium_kb",
        tool_description=(
            "Access the premium knowledge base. "
            "Pass query and payment_proof (empty string to get a payment challenge)."
        ),
    )

    def agent_handler(text: str) -> str:
        # Simplified: extract paymentProof from message if present, call tool
        payment_proof = extract_payment_proof(text)
        query         = extract_query(text)
        result        = kb_tool(query=query, payment_proof=payment_proof)
        return result

    return agent_handler


def fetch_from_knowledge_base(query: str) -> str:
    return f"KB answer for: {query}"


def extract_payment_proof(text: str) -> str:
    # Parse paymentProof from structured message text
    return ""


def extract_query(text: str) -> str:
    return text


# ── 5. AP2 protocol ───────────────────────────────────────────────────────────

gate_ap2 = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    protocol="ap2",
    network="algorand-mainnet",
    amount_microunits=10_000,
)

# Use same flask_agent / handle_request API — only the challenge header changes
# (X-AP2-Cart-Mandate instead of WWW-Authenticate)


# ── 6. x402 protocol — Edge-compatible ───────────────────────────────────────

gate_x402 = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_ALGORAND_ADDRESS",
    protocol="x402",           # X-PAYMENT-REQUIRED header
    network="algorand-mainnet",
    amount_microunits=10_000,
)


# ── 7. Multi-network: VOI / Hedera / Stellar ──────────────────────────────────

gate_voi = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_VOI_ADDRESS",
    protocol="mpp",
    network="voi-mainnet",
    amount_microunits=10_000,
)

gate_hedera = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_HEDERA_ADDRESS",
    protocol="mpp",
    network="hedera-mainnet",
    amount_microunits=10_000,
)

gate_stellar = AlgoVoiA2A(
    algovoi_key="algv_...",
    tenant_id="your-tenant-uuid",
    payout_address="YOUR_STELLAR_ADDRESS",
    protocol="mpp",
    network="stellar-mainnet",
    amount_microunits=10_000,
)


# ── 8. Full working minimal server ───────────────────────────────────────────

if __name__ == "__main__":
    print("Starting AlgoVoi A2A example server on :5000")
    print("  POST /a2a              — A2A endpoint")
    print("  GET  /.well-known/agent-card.json — agent discovery")
    app.run(debug=True, port=5000)
