# PrestaShop — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI as payment in your PrestaShop 8.x store via two payment modules: hosted checkout redirect and in-page browser-extension wallet checkout.

Full integration guide: [prestashop.md](../prestashop.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `algovoi/` | Hosted checkout module — redirects buyer to AlgoVoi payment page (Algorand, VOI, Hedera, Stellar) |
| `algovoi_ext/` | Wallet checkout module — buyer signs in-browser via Pera / Defly / Lute (Algorand + VOI) |
| `theme/` | Theme overrides for dark mode and AlgoVoi CSS |

---

## Quick start

See the integration guide above for installation and configuration.

---

Licensed under the [Business Source License 1.1](../LICENSE).
