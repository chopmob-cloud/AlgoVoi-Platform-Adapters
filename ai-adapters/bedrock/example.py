"""
AlgoVoi Bedrock Adapter — Deployment Example
=============================================
A complete, runnable payment-gated Amazon Bedrock server.

Choose your framework:
    python example.py flask      # Flask on port 5000
    python example.py fastapi    # FastAPI on port 8000

Test with curl (see bottom of this file).

Requirements:
    pip install boto3 flask fastapi uvicorn

AWS credentials:
    Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
    OR pass them directly in the AlgoVoiBedrock constructor below.

Sibling adapters must be on the path (they are if you run from this directory):
    ../../mpp-adapter/
    ../../ap2-adapter/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mpp-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ap2-adapter"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "openai"))

from bedrock_algovoi import AlgoVoiBedrock

# ── Configuration ─────────────────────────────────────────────────────────────
#
# Set these via environment variables or replace directly.
# AWS credentials can also be omitted if set via AWS_ACCESS_KEY_ID /
# AWS_SECRET_ACCESS_KEY environment variables.

gate = AlgoVoiBedrock(
    aws_access_key_id     = os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY"),
    aws_region            = os.environ.get("AWS_DEFAULT_REGION",  "us-east-1"),
    algovoi_key           = os.environ.get("ALGOVOI_KEY",         "algv_..."),
    tenant_id             = os.environ.get("TENANT_ID",           "your-tenant-uuid"),
    payout_address        = os.environ.get("PAYOUT_ADDRESS",      "YOUR_ALGORAND_ADDRESS"),
    protocol              = os.environ.get("PROTOCOL",            "mpp"),   # mpp | ap2 | x402
    network               = os.environ.get("NETWORK",             "algorand-mainnet"),
    amount_microunits     = int(os.environ.get("AMOUNT",          "10000")),  # 0.01 USDC
    model                 = os.environ.get("MODEL",               "amazon.nova-pro-v1:0"),
)


# ── Flask ─────────────────────────────────────────────────────────────────────

def create_flask_app():
    from flask import Flask, request, jsonify, Response
    app = Flask(__name__)

    @app.route("/ai/chat", methods=["POST"])
    def chat():
        """
        Payment-gated Bedrock chat endpoint.

        Without payment:
            POST /ai/chat  ->  402 + WWW-Authenticate (MPP) or X-AP2-Cart-Mandate
        With valid payment proof:
            POST /ai/chat  ->  200 {"content": "..."}
        """
        body   = request.get_json(silent=True) or {}
        result = gate.check(dict(request.headers), body)

        if result.requires_payment:
            flask_body, status, headers = result.as_flask_response()
            return Response(flask_body, status=status, headers=headers,
                            mimetype="application/json")

        messages = body.get("messages", [])
        content  = gate.complete(messages)
        return jsonify({"content": content})

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


# ── FastAPI ───────────────────────────────────────────────────────────────────

def create_fastapi_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response

    app = FastAPI(title="AlgoVoi Bedrock Gateway")

    @app.post("/ai/chat")
    async def chat(req: Request):
        """
        Payment-gated Bedrock chat endpoint.

        Without payment:
            POST /ai/chat  ->  402 + WWW-Authenticate (MPP) or X-AP2-Cart-Mandate
        With valid payment proof:
            POST /ai/chat  ->  200 {"content": "..."}
        """
        body   = await req.json()
        result = gate.check(dict(req.headers), body)

        if result.requires_payment:
            status, headers, body_bytes = result.as_wsgi_response()
            return Response(content=body_bytes, status_code=402,
                            headers=dict(headers))

        messages = body.get("messages", [])
        content  = gate.complete(messages)
        return JSONResponse({"content": content})

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "flask"

    if mode == "fastapi":
        import uvicorn
        app = create_fastapi_app()
        print("Starting FastAPI on http://0.0.0.0:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        app = create_flask_app()
        print("Starting Flask on http://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=False)  # nosec B201


# ── curl test commands ────────────────────────────────────────────────────────
#
# 1. Health check
# ---------------
# curl http://localhost:5000/health
#
#
# 2. Request without payment — expect 402
# ----------------------------------------
# curl -s -i -X POST http://localhost:5000/ai/chat \
#   -H "Content-Type: application/json" \
#   -d '{"messages": [{"role": "user", "content": "Hello"}]}'
#
# Response (MPP):
#   HTTP/1.1 402 Payment Required
#   WWW-Authenticate: Payment realm="API Access", id="<challenge-id>",
#     method="algorand-mainnet", amount="10000", asset="31566704",
#     payto="YOUR_ALGORAND_ADDRESS"
#
# Response (AP2):
#   HTTP/1.1 402 Payment Required
#   X-AP2-Cart-Mandate: <base64-encoded CartMandate>
#
#
# 3. Request with valid MPP payment proof — expect 200
# -----------------------------------------------------
# PROOF=$(python3 -c "
# import base64, json
# print(base64.b64encode(json.dumps({
#   'network': 'algorand-mainnet',
#   'payload': {'txId': 'YOUR_TX_ID'}
# }).encode()).decode())
# ")
#
# curl -s -X POST http://localhost:5000/ai/chat \
#   -H "Content-Type: application/json" \
#   -H "Authorization: Payment $PROOF" \
#   -d '{"messages": [
#         {"role": "system", "content": "You are a helpful assistant."},
#         {"role": "user",   "content": "Hello"}
#       ]}'
#
# Response:
#   {"content": "Hello! I'm Amazon Nova. How can I help you today?"}
#
#
# 4. Use a different Bedrock model
# ---------------------------------
# Set MODEL env var before starting:
#   export MODEL="anthropic.claude-3-5-sonnet-20241022-v2:0"
#   python example.py flask
#
# Or override at call time in the route handler:
#   content = gate.complete(messages, model="amazon.nova-lite-v1:0")
