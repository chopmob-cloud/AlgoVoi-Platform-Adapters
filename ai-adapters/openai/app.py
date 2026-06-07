from dotenv import load_dotenv
load_dotenv()

import os
from openai_algovoi import AlgoVoiOpenAI
from flask import Flask, request, jsonify, Response

gate = AlgoVoiOpenAI(
    openai_key        = os.environ["OPENAI_KEY"],
    algovoi_key       = os.environ["ALGOVOI_KEY"],
    tenant_id         = os.environ["TENANT_ID"],
    payout_address    = os.environ["PAYOUT_ADDRESS"],
    protocol          = os.environ.get("PROTOCOL",  "x402"),
    network           = os.environ.get("NETWORK",   "algorand-mainnet"),
    amount_microunits = int(os.environ.get("AMOUNT", "10000")),
)

app = Flask(__name__)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body   = request.get_json() or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        b, s, h = result.as_flask_response()
        return Response(b, status=s, headers=h)
    return jsonify({"content": gate.complete(body["messages"])})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(port=5000)
