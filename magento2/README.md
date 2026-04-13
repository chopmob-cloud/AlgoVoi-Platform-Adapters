# Magento 2 — AlgoVoi Payment Adapter

Accepts USDC on Algorand and aUSDC on VOI as payment in your Magento 2 store via two installable payment method modules: hosted checkout and in-page browser-extension checkout.

Full integration guide: [magento.md](../magento.md)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `Algovoi/Payment/Model/AlgovoiPayment.php` | Core payment method model |
| `Algovoi/Payment/Helper/ApiHelper.php` | AlgoVoi REST API client |
| `Algovoi/Payment/Controller/Checkout/Redirect.php` | Hosted checkout redirect controller |
| `Algovoi/Payment/Controller/Webhook/Notify.php` | Webhook handler |
| `Algovoi/Payment/Model/Ui/ConfigProvider.php` | Frontend config provider |
| `Algovoi/Payment/etc/` | Module configuration (di.xml, config.xml, module.xml, etc.) |
| `Algovoi/Payment/view/` | Frontend layout, JS component, and payment template |
| `Algovoi/Payment/registration.php` | Module registration |
| `Algovoi/Payment/composer.json` | Composer package manifest |

---

## Quick start

See the integration guide above for installation and configuration.

---

Licensed under the [Business Source License 1.1](../LICENSE).
