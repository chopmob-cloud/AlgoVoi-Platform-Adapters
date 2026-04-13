# Wormhole — AlgoVoi Payment Adapter

Bridges USDC from any Wormhole-supported chain (Ethereum, Solana, Base, Polygon, Avalanche, Arbitrum) to Algorand or VOI for AlgoVoi settlement, with no manual swap or CEX required.

Full integration guide: [wormhole.md](../wormhole.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `wormhole_algovoi.py` | Adapter — polls Wormhole bridge status for confirmed USDC transfers and creates AlgoVoi settlement links |
| `test_wormhole.py` | Integration test suite |

---

## Quick start

```python
from wormhole_algovoi import WormholeAlgoVoi

adapter = WormholeAlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
    target_chain="algorand",  # or "voi"
)
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
