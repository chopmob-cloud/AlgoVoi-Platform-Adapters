# Native PHP — AlgoVoi Payment Adapter

Zero-dependency PHP library for integrating AlgoVoi payments (hosted checkout, in-page wallet, and webhook verification) into any PHP application without requiring Composer or external packages.

Full integration guide: [native-php — see root README](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `algovoi.php` | Client library — hosted checkout, extension payment, webhook HMAC verification |
| `example.php` | Usage examples for hosted checkout, extension payment, and webhook handling |

---

## Quick start

```php
require_once __DIR__ . '/algovoi.php';

$av = new AlgoVoi([
    'api_base'       => 'https://api1.ilovechicken.co.uk',
    'api_key'        => 'algv_YOUR_API_KEY',
    'tenant_id'      => 'YOUR_TENANT_ID',
    'webhook_secret' => 'YOUR_WEBHOOK_SECRET',
]);

$link = $av->createPaymentLink([
    'amount'    => 9.99,
    'currency'  => 'USD',
    'order_ref' => 'ORDER-001',
]);
header('Location: ' . $link['url']);
```

---

Licensed under the [Business Source License 1.1](../LICENSE).
