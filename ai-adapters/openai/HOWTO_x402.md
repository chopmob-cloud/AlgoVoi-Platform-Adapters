# x402 payments via OpenAI + AlgoVoi

## Setup

**1. Create an account**
Sign up at algovoi.co.uk and copy your **Tenant ID** and **API key**.

**2. Download the adapter**
Grab `openai_algovoi.py` from:
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

**3. Install dependencies**
```bash
pip install openai flask python-dotenv
```

**4. Create your `.env` file**
```bash
cp .env.example .env
# then edit .env and fill in your keys
```

```ini
OPENAI_KEY=sk-...
ALGOVOI_KEY=algv_...
TENANT_ID=your-tenant-uuid
PAYOUT_ADDRESS=YOUR_ALGORAND_ADDRESS
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
