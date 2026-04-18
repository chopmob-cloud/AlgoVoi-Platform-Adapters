# Shopware 6 — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI as payment in your Shopware 6 store via two installable plugins: hosted checkout and in-page browser-extension wallet checkout.

Full integration guide: [shopware.md](../shopware.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `AlgovoiPayment/` | Payment plugin — hosted and wallet payment handlers, webhook controller, API helper |
| `AlgovoiTheme/` | Optional storefront theme plugin with AlgoVoi branding |
| `algovoi.css` | Shared payment form styles |
| `import-products.php` | Utility script for bulk product import |

---

## Quick start

1. Download from the [latest release](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest):
   - [`algovoi-shopware.zip`](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest/download/algovoi-shopware.zip) — payment plugin (required)
   - [`algovoi-shopware-theme.zip`](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/releases/latest/download/algovoi-shopware-theme.zip) — optional theme
2. Shopware Admin → Extensions → My extensions → Upload extension → Install → Activate
3. Settings → Payment → AlgoVoi → enter your `algvc_...` Cloud key + API Base `https://cloud.algovoi.co.uk`

See the integration guide above for full configuration options.

---

Licensed under the [Business Source License 1.1](../LICENSE).
