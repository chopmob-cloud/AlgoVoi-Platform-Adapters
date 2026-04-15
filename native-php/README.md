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

// Hosted checkout — redirect the customer to AlgoVoi's payment page.
$result = $av->hostedCheckout(
    9.99,                                 // amount
    'USD',                                // currency
    'Order #1042',                        // label
    'algorand_mainnet',                   // network
    'https://yoursite.com/payment-return' // redirect URL after payment
);
if ($result === null) {
    http_response_code(500); exit('Payment could not be initiated.');
}
$_SESSION['algovoi_token'] = $result['token'];
header('Location: ' . $result['checkout_url']);
exit;
```

When the customer returns, **always** call `verifyHostedReturn()` before
marking the order as paid — this prevents the cancel-bypass attack:

```php
if ($av->verifyHostedReturn($_SESSION['algovoi_token'] ?? '')) {
    // Mark order paid
} else {
    // Order is still pending / cancelled
}
```

> **Security notes (v1.1.0)**
> - All outbound requests refuse to run over plain HTTP — `api_base`
>   must start with `https://`.
> - `verifyWebhook` requires a non-empty `webhook_secret`, caps the
>   inbound body at 64 KB, and only returns when the body is a JSON
>   object (scalar bodies are rejected).
> - `createPaymentLink` rejects non-finite amounts and `redirect_url`
>   schemes other than `https`.
> - `verifyExtensionPayment` length-caps both `token` and `tx_id`
>   (200 chars each).

---

Licensed under the [Business Source License 1.1](../LICENSE).
