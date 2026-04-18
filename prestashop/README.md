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

1. Download one or both from the [latest release](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest):
   - [`algovoi-prestashop.zip`](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest/download/algovoi-prestashop.zip) — hosted checkout
   - [`algovoi-prestashop-extension.zip`](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest/download/algovoi-prestashop-extension.zip) — in-page wallet checkout
2. PrestaShop Back Office → Modules → Module Manager → Upload a module
3. Configure → enter your `algvc_...` Cloud key + API Base `https://cloud.algovoi.co.uk`

See the integration guide above for full configuration options.

---

Licensed under the [Business Source License 1.1](../LICENSE).
