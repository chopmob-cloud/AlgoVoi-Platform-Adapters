# x402 payments via OpenAI + AlgoVoi

## Setup

**1. Create an account**
Sign up at algovoi.co.uk and copy your **Tenant ID** and **API key**.

**2. Download the adapter**
Grab `openai_algovoi.py` from:
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

**3. Install dependencies**
```bash
pip install openai flask
```

**4. Create app.py**
```python
from openai_algovoi import AlgoVoiOpenAI
from flask import Flask, request, jsonify, Response

gate = AlgoVoiOpenAI(
    openai_key        = "sk-...",
    algovoi_key       = "algv_...",   # your AlgoVoi API key
    tenant_id         = "...",        # your Tenant ID
    payout_address    = "...",        # your wallet address
    protocol          = "x402",
    network           = "algorand-mainnet",
    amount_microunits = 10000         # 0.01 USDC per call
)

app = Flask(__name__)

@app.route("/ai/chat", methods=["POST"])
def chat():
    body = request.get_json() or {}
    result = gate.check(dict(request.headers), body)
    if result.requires_payment:
        b, s, h = result.as_flask_response()
        return Response(b, status=s, headers=h)
    return jsonify({"content": gate.complete(body["messages"])})

app.run(port=5000)
```

**5. Run it**
```bash
python app.py
```

---

## How it works

- No payment header → `402` + x402 challenge
- Client pays on-chain → sends `tx_id` as base64 proof
- `api1.ilovechicken.co.uk` verifies the TX on-chain
- Verified → OpenAI is called → `200` + response

---

## Supported networks

```python
network="algorand-mainnet"  # USDC  (ASA 31566704)
network="voi-mainnet"       # aUSDC (ARC200 302190)
network="hedera-mainnet"    # USDC  (HTS 0.0.456858)
network="stellar-mainnet"   # USDC  (Circle)
```

Only the `network` value changes — everything else stays the same.
