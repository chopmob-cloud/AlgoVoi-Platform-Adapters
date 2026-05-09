# Native PHP — AlgoVoi Payment Adapter

Zero-dependency PHP library for integrating AlgoVoi payments (hosted checkout, in-page wallet, and webhook verification) into any PHP application without requiring Composer or external packages.

Full integration guide: [native-php — see root README](https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters)
https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters

---

## Files

| File | Description |
|------|-------------|
| `algovoi.php` | Client library — hosted checkout, extension payment, webhook HMAC verification, Tier 2 recurring |
| `example.php` | Usage examples for hosted checkout, extension payment, and webhook handling |
| `recurring_test.php` | 18 stdlib-only unit tests for Tier 2 (run with `php recurring_test.php`) |

---

## Quick start — Tier 1 (one-shot payment)

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

## Quick start — Tier 2 (recurring / standing authority)

Tier 2 is "customer signs once, AlgoVoi auto-pulls per cycle". Requires an
existing subscription UUID (create one via the dashboard or `POST /v1/subscriptions`).

```php
// 1. Create a standing authority for a monthly $10 subscription.
$resp = $av->createRecurringAuthority([
    'subscription_id'         => 'YOUR_SUBSCRIPTION_UUID',
    'chain'                   => 'algorand_mainnet',  // or any of the 7 chains
    'customer_wallet_address' => 'CUSTOMER_ALGO_ADDRESS',
    'cap_amount_minor'        => 120_000_000,          // $120 cap (6 decimals)
    'cap_period_seconds'      => 365 * 86400,          // 1-year window
    'per_cycle_amount_minor'  => 10_000_000,           // $10/month per pull
    'asset'                   => 'USDC',
]);
// $resp['customer_signing_payload'] — hand to the customer's wallet UI

// 2. After on-chain landing, confirm (AlgoVoi's hosted widget does this for you):
$auth = $av->confirmAuthority($resp['authority']['id'], [
    'on_chain_address' => 'app:12345678',  // format varies by chain
]);

// 3. Lifecycle management:
$auth = $av->getAuthority($authorityId);
$auth = $av->pauseAuthority($authorityId);
$auth = $av->resumeAuthority($authorityId);
$auth = $av->revokeAuthority($authorityId);  // on-chain revocation

// 4. Webhook classification:
$payload = $av->verifyWebhook($rawBody, $_SERVER['HTTP_X_ALGOVOI_SIGNATURE_V1'] ?? '');
if ($payload !== null && AlgoVoi::isRecurringEvent($payload)) {
    $eventType = $payload['event_type'];
    // "subscription.charged", "subscription.payment_failed",
    // "recurring.authority_activated", etc.
}
```

Stellar uses 7-decimal USDC precision (`1_200_000_000` = 120 USDC).
All other chains use 6 decimals.

See [`Recurr/merchant-examples/php.php`](../Recurr/merchant-examples/php.php)
for a full runnable example and
[`Recurr/README.md`](../Recurr/README.md) for the chain matrix.

---

Licensed under the [Business Source License 1.1](../LICENSE).
