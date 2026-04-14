from openai_algovoi import AlgoVoiOpenAI
from flask import Flask, request, jsonify, Response

gate = AlgoVoiOpenAI(
    openai_key        = "sk-...",           # ← your OpenAI key
    algovoi_key       = "algv_...",         # ← your AlgoVoi API key
    tenant_id         = "your-tenant-uuid", # ← your Tenant ID
    payout_address    = "YOUR_ALGORAND_ADDRESS", # ← your wallet address
    protocol          = "x402",
    network           = "algorand-mainnet", # algorand-mainnet | voi-mainnet | hedera-mainnet | stellar-mainnet
    amount_microunits = 10000,              # 0.01 USDC per call
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
