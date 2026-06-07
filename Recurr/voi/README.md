# VOI — SpendingCapVault (Tier 2)

**Wire format:** `algorand_spending_cap_vault_v1` (same as Algorand)
**Asset:** native VOI coin (ASA-id sentinel `0`, 6 decimals)
**Wallets:** Lute, Kibisis, any AVM-compatible wallet

VOI is AVM-compatible (same virtual machine as Algorand), so it uses
the **same SpendingCapVault smart contract** and the **same wire format**
as Algorand. The only differences are at the network layer:

| Aspect | Algorand | VOI |
|---|---|---|
| Asset | USDC ASA `31566704` | Native VOI coin (ASA-id `0`) |
| Decimals | 6 | 6 |
| Algod RPC | `mainnet-api.algonode.cloud` | `mainnet-api.voi.nodely.io` |
| Genesis | `mainnet-v1.0` | `voimain-v1.0` |
| Action group | 6 actions | 6 actions (same) |

---

## Asset support

The Tier 2 v1 surface on VOI supports the **native VOI coin**.
ARC-200 aUSDC (Aramid-bridged USDC) is on the post-£150k roadmap —
ARC-200 tokens require a different asset-transfer code path than
ASA tokens, and the SpendingCapVault contract needs an ARC-200
extension to recognise them.

For native VOI authorisations, pass `asset="VOI"` in the
`create_recurring_authority` call. The gateway resolves to ASA-id `0`
(the AVM sentinel for the native coin).

---

## Customer signing payload

Identical structure to [Algorand](../algorand/README.md), with these
field differences:

```json
{
  "version": "algorand_spending_cap_vault_v1",
  "asa_id":  0,
  "vault_template": { ... },
  ...
}
```

`asa_id: 0` tells the wallet "this is the native coin, not an ASA"
— action 6 (`fund_vault_usdc`, despite the misleading name) emits
a `payment` transaction instead of an `axfer`.

---

## Wallet-side reference

See [`../algorand/README.md`](../algorand/README.md) for the full
6-action flow. Use the same `algosdk` library, just point at VOI's
algod node:

```python
from algosdk.v2client import algod

client = algod.AlgodClient("", "https://mainnet-api.voi.nodely.io")
# ... rest of the flow is identical to Algorand
```

For the `fund_vault_usdc` action, branch on `asa_id`:

```python
if template["asa_id"] == 0:
    # Native VOI — use Payment, not AssetTransfer
    fund_txn = transaction.PaymentTxn(
        sender=customer, sp=sp,
        receiver=vault_app_address,
        amt=template["vault_funding_asa_units"],
    )
else:
    # ASA — use AssetTransfer (Algorand path)
    fund_txn = transaction.AssetTransferTxn(...)
```

The `fund_vault_algo` action (action 2) is also a Payment, but it's
the MBR top-up (200_000 base units) — not the cap-amount funding.
Both actions emit Payment txns when `asa_id == 0`.

---

## Common pitfalls

- **VOI is AVM but with different fees.** Min fee is the same
  (1000 base units = 0.001 VOI), but consensus parameters differ
  slightly. Use VOI's algod node for `suggested_params()`, not
  Algorand's.
- **Wallet support is narrower.** Pera and Defly do not support
  VOI mainnet by default (they're Algorand-focused). Lute and
  Kibisis are the canonical VOI wallets. Confirm which wallets
  your customers use before promising VOI support in your UX.
- **No USDC on VOI today.** If you need a stablecoin, use a
  different chain (Algorand / Base / Solana / Hedera / Stellar).
  VOI is for native-coin subscriptions until ARC-200 ships.

---

## Related

- [`../algorand/`](../algorand/) — full SpendingCapVault flow + 6-action group
- Native VOI on AlgoVoi Tier 1: see `../../native-python/algovoi.py`'s
  `extension_checkout(network="voi_mainnet", ...)` for one-shot payments
