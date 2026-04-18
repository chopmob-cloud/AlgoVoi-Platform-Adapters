# OpenCart — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI as payment in your OpenCart 4 store via two payment methods: hosted checkout redirect and in-page browser-extension checkout.

Full integration guide: [opencart.md](../opencart.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `algovoi/` | Hosted checkout extension — redirects customer to AlgoVoi payment page |
| `algovoi_ext/` | Extension checkout — in-page wallet payment via the AlgoVoi browser extension |
| `install.json` | OpenCart extension manifest |

---

## Quick start

1. Download one or both from the [latest release](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest):
   - [`algovoi-opencart.zip`](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest/download/algovoi-opencart.zip) — hosted checkout
   - [`algovoi-opencart-extension.zip`](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest/download/algovoi-opencart-extension.zip) — in-page wallet checkout
2. OpenCart Admin → Extensions → Installer → Upload → Install
3. Extensions → Payments → AlgoVoi → Edit → enter your `algvc_...` Cloud key + API Base `https://cloud.algovoi.co.uk`

See the integration guide above for full configuration options.

---

Licensed under the [Business Source License 1.1](../LICENSE).
