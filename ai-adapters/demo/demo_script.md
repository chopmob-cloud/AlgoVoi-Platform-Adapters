# AlgoVoi AI Adapters — Demo Script

A step-by-step script for recording a terminal demo with `asciinema`.
Run each command in order after the server is started.

---

## Setup

```bash
# Terminal 1 — start the server (Claude adapter, MPP, Algorand mainnet)
cd ai-adapters/claude
export ANTHROPIC_KEY="sk-ant-..."
export ALGOVOI_KEY="algv_..."
export TENANT_ID="your-tenant-uuid"
export PAYOUT_ADDRESS="YOUR_ALGORAND_ADDRESS"
export PROTOCOL="mpp"
python example.py flask
```

```bash
# Terminal 2 — record the demo
asciinema rec algovoi_demo.cast --title "AlgoVoi — Payment-Gated AI APIs"
```

---

## Scene 1 — Health check

```bash
curl http://localhost:5000/health
```

Expected:
```json
{"status": "ok"}
```

---

## Scene 2 — Request without payment (402)

```bash
curl -s -i -X POST http://localhost:5000/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

Expected:
```
HTTP/1.1 402 Payment Required
WWW-Authenticate: Payment realm="API Access", id="...",
  method="algorand-mainnet", amount="10000", asset="31566704",
  payto="YOUR_ALGORAND_ADDRESS"
```

---

## Scene 3 — Build a payment proof

```bash
PROOF=$(python3 -c "
import base64, json
print(base64.b64encode(json.dumps({
  'network': 'algorand-mainnet',
  'payload': {'txId': 'YOUR_TX_ID'}
}).encode()).decode())
")
echo "Proof: $PROOF"
```

---

## Scene 4 — Request with payment (200)

```bash
curl -s -X POST http://localhost:5000/ai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Payment $PROOF" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user",   "content": "What is AlgoVoi in one sentence?"}
    ]
  }' | python3 -m json.tool
```

Expected:
```json
{
    "content": "AlgoVoi is a payment gateway that lets developers charge per API call using USDC on Algorand, VOI, Hedera, or Stellar."
}
```

---

## Scene 5 — Same proof, different model

```bash
curl -s -X POST http://localhost:5000/ai/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Payment $PROOF" \
  -d '{
    "messages": [{"role": "user", "content": "Say hello in 5 languages."}],
    "model": "claude-haiku-4-5"
  }' | python3 -m json.tool
```

---

## Convert recording

```bash
# Stop recording with Ctrl-D, then:

# GIF — for GitHub READMEs
agg algovoi_demo.cast algovoi_demo.gif

# MP4 — for YouTube / social
ffmpeg -i algovoi_demo.gif -movflags faststart -pix_fmt yuv420p algovoi_demo.mp4
```

---

## Tips

- Use `--overwrite` flag with `asciinema rec` to re-record without renaming
- Set terminal width to 120 columns for readability: `resize -s 40 120`
- Use a dark theme (VS Code Dark+ or Dracula) — looks better in recordings
- Pause between commands — asciinema replays at real speed
- `agg` supports `--theme dracula`, `--font-size 18`, `--cols 120` flags
