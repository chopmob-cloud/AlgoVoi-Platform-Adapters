# Algorand — SpendingCapVault (Tier 2)

**Wire format:** `algorand_spending_cap_vault_v1`
**Asset:** USDC (ASA `31566704`, 6 decimals) on mainnet · USDC ASA on testnet
**Wallets:** Pera, Defly, Lute, Daffi (any algosdk-compatible signer)

Algorand's Tier 2 primitive is the **SpendingCapVault** smart contract
— an ARC-4 application the customer deploys for themselves. The vault
holds a USDC balance and exposes a `pull` method that AlgoVoi's
facilitator calls per cycle. The vault enforces three caps on-chain:

1. **`max_per_txn`** — per-pull ceiling (matches `per_cycle_amount_minor`)
2. **`daily_cap`** — rolling 24h limit (derived from `cap_amount / cycles`)
3. **Allowlisted recipient** — the merchant's payout address; vault rejects
   pulls to any other recipient

This means even if AlgoVoi's facilitator key were compromised, an
attacker could not drain the vault — funds can only flow to the
specific merchant the customer authorised.

---

## The 6-action atomic group

When the customer signs, they sign a single atomic transaction group
of 6 actions. All 6 must succeed or none does. The wallet walks the
customer through this group as a unit (most wallets render it as
"Sign 6 transactions").

| # | Action id | Method | Description |
|---|---|---|---|
| 1 | `deploy_vault` | App `create` | Deploys the SpendingCapVault contract owned by the customer |
| 2 | `fund_vault_algo` | `payment` (200_000 µALGO) | Funds vault MBR for box storage |
| 3 | `vault_opt_in_asa` | App `opt_in_asa` | Vault opts into USDC ASA |
| 4 | `register_agent` | App `add_agent` | Registers AlgoVoi facilitator with `max_per_txn` + `daily_cap` |
| 5 | `register_recipient` | App `add_recipient` | Allowlists merchant payout address |
| 6 | `fund_vault_usdc` | `axfer` (cap_amount USDC) | Funds vault with the total subscription budget |

The customer signs all 6; the group is submitted as one atomic unit.
After landing, AlgoVoi marks the authority `active` and the cycle
reaper begins pulling.

---

## Customer signing payload (sample)

```json
{
  "version": "algorand_spending_cap_vault_v1",
  "vault_template": {
    "create_args": {
      "global_max_per_txn":     "10000000",
      "global_daily_cap":       "10000000",
      "global_max_asa_per_txn": "10000000",
      "allowlist_enabled":      "1"
    }
  },
  "vault_funding_micro_algo":  200000,
  "vault_funding_asa_units":   120000000,
  "asa_id":                    31566704,
  "facilitator_address":       "ALGOVOI_FACILITATOR_G_ADDR_58_CHARS",
  "merchant_payout_address":   "MERCHANT_PAYOUT_G_ADDR_58_CHARS",
  "customer_address":          "CUSTOMER_G_ADDR_58_CHARS",
  "per_cycle_amount_atomic":   10000000,
  "daily_cap_atomic":          10000000,
  "cap_amount_atomic":         120000000,
  "actions": [
    {"id": "deploy_vault",       "method": "create",         "signer": "customer"},
    {"id": "fund_vault_algo",    "method": "payment",        "signer": "customer",
     "amount_micro_algo": 200000},
    {"id": "vault_opt_in_asa",   "method": "opt_in_asa",     "signer": "customer",
     "args": {"asset": 31566704}},
    {"id": "register_agent",     "method": "add_agent",      "signer": "customer",
     "args": {"agent": "ALGOVOI_FACILITATOR_G_ADDR_58_CHARS",
              "max_per_txn": 10000000, "daily_cap": 10000000}},
    {"id": "register_recipient", "method": "add_recipient",  "signer": "customer",
     "args": {"recipient": "MERCHANT_PAYOUT_G_ADDR_58_CHARS",
              "max_per_txn": 10000000, "daily_cap": 10000000}},
    {"id": "fund_vault_usdc",    "method": "asset_transfer", "signer": "customer",
     "args": {"asset": 31566704, "amount": 120000000}}
  ]
}
```

---

## Wallet-side reference (Python + algosdk)

The wallet (or your frontend doing the wallet job) consumes this
template and constructs 6 real Algorand transactions, groups them,
asks the customer to sign, and submits to the network.

```python
"""Reference wallet-side flow for Algorand Tier 2 authorisation.

Requires: pip install py-algorand-sdk

This is what the AlgoVoi widget does internally for tenants using
the hosted authorisation page. Tenants who self-host the wallet UI
can use this as a reference for any algosdk-based wallet (Pera,
Defly, Lute, Daffi, etc.).
"""

from algosdk import transaction, encoding
from algosdk.v2client import algod

# 1. Receive the template from the gateway
#    (via POST /v1/recurring/authorities response)
template = response["customer_signing_payload"]
assert template["version"] == "algorand_spending_cap_vault_v1"

# 2. Connect to algod
client = algod.AlgodClient("", "https://mainnet-api.algonode.cloud")
sp = client.suggested_params()

customer = template["customer_address"]
asa_id   = template["asa_id"]
funding_micro = template["vault_funding_micro_algo"]
funding_asa   = template["vault_funding_asa_units"]

# 3. Build the 6 transactions corresponding to template["actions"]

# Action 1: deploy_vault — ApplicationCreate with vault_template's create_args
deploy_txn = transaction.ApplicationCreateTxn(
    sender=customer,
    sp=sp,
    on_complete=transaction.OnComplete.NoOpOC,
    approval_program=...,    # SpendingCapVault TEAL bytecode
    clear_program=...,       # standard clear-state
    global_schema=transaction.StateSchema(num_uints=8, num_byte_slices=2),
    local_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
    app_args=[...],          # template["vault_template"]["create_args"], serialised
)

# Action 2: fund_vault_algo — Payment from customer to vault MBR
# (vault address derives from the application id once deploy_vault confirms,
#  so this txn's receiver is filled in by the wallet AFTER deploy is in the group)
fund_algo_txn = transaction.PaymentTxn(
    sender=customer,
    sp=sp,
    receiver=...,            # vault application address
    amt=funding_micro,
)

# Action 3: vault_opt_in_asa — ApplicationCall(opt_in_asa) with asa_id arg
opt_in_txn = transaction.ApplicationCallTxn(
    sender=customer,
    sp=sp,
    index=...,               # vault app id
    on_complete=transaction.OnComplete.NoOpOC,
    app_args=[b"opt_in_asa", asa_id.to_bytes(8, "big")],
    foreign_assets=[asa_id],
)

# Action 4: register_agent — ApplicationCall(add_agent, ...)
add_agent_txn = transaction.ApplicationCallTxn(
    sender=customer, sp=sp, index=..., on_complete=transaction.OnComplete.NoOpOC,
    app_args=[
        b"add_agent",
        encoding.decode_address(template["facilitator_address"]),
        template["per_cycle_amount_atomic"].to_bytes(8, "big"),
        template["daily_cap_atomic"].to_bytes(8, "big"),
    ],
)

# Action 5: register_recipient — ApplicationCall(add_recipient, ...)
add_recipient_txn = transaction.ApplicationCallTxn(
    sender=customer, sp=sp, index=..., on_complete=transaction.OnComplete.NoOpOC,
    app_args=[
        b"add_recipient",
        encoding.decode_address(template["merchant_payout_address"]),
        template["per_cycle_amount_atomic"].to_bytes(8, "big"),
        template["daily_cap_atomic"].to_bytes(8, "big"),
    ],
)

# Action 6: fund_vault_usdc — AssetTransfer of cap_amount USDC to vault
fund_asa_txn = transaction.AssetTransferTxn(
    sender=customer, sp=sp,
    receiver=...,            # vault application address
    amt=funding_asa,
    index=asa_id,
)

# 4. Group them atomically
group = [deploy_txn, fund_algo_txn, opt_in_txn,
         add_agent_txn, add_recipient_txn, fund_asa_txn]
transaction.assign_group_id(group)

# 5. Hand to customer wallet for signing.
#    With Pera/Defly/Lute/Daffi: encode each as msgpack + show in wallet UI.
#    Wallet returns 6 SignedTransaction blobs.
signed = wallet.sign_group(group)   # provider-specific call

# 6. Submit
tx_id = client.send_transactions(signed)
client.status_after_block(client.status()["last-round"] + 4)

# 7. Tell AlgoVoi the authority is active
#    on_chain_address format: "app:<application_id>"
av.confirm_authority(
    authority_id=response["authority"]["id"],
    on_chain_address=f"app:{deploy_txn.application_id}",
)
```

For TypeScript wallet integration, the same flow with `algosdk` (npm).
The action-id list and template field names are identical across
language SDKs.

---

## Per-cycle pulls (informational)

After the authority is active, the cycle reaper calls the vault's
`pull` method per cycle. This is internal to AlgoVoi — your wallet
integration doesn't need to handle pulls. They show up to the customer
as outgoing USDC transfers from the vault to the merchant payout
address; to AlgoVoi as `subscription.charged` webhook events.

The vault enforces:
- `max_per_txn` ≥ pull amount
- 24h rolling sum ≤ `daily_cap`
- recipient ∈ allowlist (just the merchant's payout address)

If any check fails, the call reverts and the pull is recorded as
`subscription.payment_failed` for retry.

---

## Common pitfalls

- **Box MBR.** The vault uses boxes for its agent + recipient state.
  `vault_funding_micro_algo` = 200_000 µALGO covers the MBR for the
  default footprint. If you need more agents/recipients later, the
  customer must top up.
- **Group atomicity.** All 6 actions must commit together. If any
  fails (e.g. customer's USDC balance < `cap_amount`), nothing lands
  and the wallet shows the error.
- **`cap_period_seconds < 86400`.** The gateway rejects authorities
  with a cap window shorter than 1 day. Use 30/90/365 × 86400 as
  typical values.
- **Network selection.** Mainnet uses ASA `31566704`; testnet uses
  the testnet USDC ASA. The gateway routes per `chain` field — if
  `chain="algorand_testnet"` you'll get the testnet asa id.

---

## Related

- **VOI** uses the same SpendingCapVault contract (AVM-compatible).
  See [`../voi/`](../voi/).
- **Merchant side:** see [`../merchant-examples/python.py`](../merchant-examples/python.py)
  or [`../../native-python/`](../../native-python/) for the merchant
  HTTP-wrapper integration.
