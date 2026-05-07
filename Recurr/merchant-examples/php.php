<?php
/**
 * AlgoVoi Tier 2 — PHP merchant-side example.
 *
 * Runnable reference showing the full Tier 2 lifecycle from the
 * merchant's perspective. The wallet-side flow (where the customer
 * actually signs the on-chain authorisation) is documented per chain
 * in ../algorand/, ../voi/, ../evm/, ../solana/, ../hedera/, ../stellar/.
 *
 * Uses the native-php adapter at ../../native-php/algovoi.php (v1.2.0+) —
 * the chain-agnostic merchant HTTP wrapper. Zero composer dependencies.
 *
 * Run:
 *     php php.php
 *
 * Replace api_key / tenant_id / webhook_secret + an existing
 * subscription_id below to actually exercise the lifecycle.
 */

declare(strict_types=1);

require_once __DIR__ . '/../../native-php/algovoi.php';

// ---------------------------------------------------------------------------
// Configure
// ---------------------------------------------------------------------------

$av = new AlgoVoi([
    'api_base'       => 'https://api1.ilovechicken.co.uk',
    'api_key'        => 'algv_REPLACE_ME',
    'tenant_id'      => 'REPLACE_ME_UUID',
    'webhook_secret' => 'whsec_REPLACE_ME',
]);

// ---------------------------------------------------------------------------
// Step 1 — Create a Tier 2 standing authority for an existing subscription
// ---------------------------------------------------------------------------

/**
 * $10/month subscription, 12-month standing authority, on the customer's
 * chosen chain.
 */
function exampleCreateAuthority(
    AlgoVoi $av,
    string $subscriptionId,
    string $customerWallet,
    string $chain
): ?array {
    if (!AlgoVoi::isRecurringNetwork($chain)) {
        throw new InvalidArgumentException("Unsupported chain: $chain");
    }

    // Cap amounts depend on chain decimals.
    // Most chains: 6 decimals. Stellar: 7 decimals.
    if (str_starts_with($chain, 'stellar_')) {
        $perCycle = 10 * 10_000_000;   // 10 USDC at 7 decimals
        $totalCap = 120 * 10_000_000;
    } else {
        $perCycle = 10 * 1_000_000;    // 10 USDC at 6 decimals
        $totalCap = 120 * 1_000_000;
    }

    $resp = $av->createRecurringAuthority([
        'subscription_id'         => $subscriptionId,
        'chain'                   => $chain,
        'customer_wallet_address' => $customerWallet,
        'cap_amount_minor'        => $totalCap,
        'cap_period_seconds'      => 365 * 86400,
        'per_cycle_amount_minor'  => $perCycle,
        'asset'                   => 'USDC',
        'metadata'                => [
            'plan'           => 'monthly_pro',
            'customer_email' => 'alice@example.com',
        ],
    ]);

    if ($resp === null) {
        throw new RuntimeException('Authority creation failed (check logs / API key)');
    }
    echo "[create] authority_id = {$resp['authority']['id']}\n";
    echo "[create] status       = {$resp['authority']['status']}\n";
    echo "[create] template ver = {$resp['customer_signing_payload']['version']}\n";

    // Hand $resp['customer_signing_payload'] to your frontend wallet UI.
    // The per-chain folders in this directory have wallet-side reference code.
    return $resp;
}

// ---------------------------------------------------------------------------
// Step 2 — After the customer's wallet signs and on-chain auth lands
// ---------------------------------------------------------------------------

/**
 * `$onChainHandle` format depends on the chain:
 *     Algorand / VOI : "app:<application_id>"
 *     EVM            : "0x<tx_hash>"
 *     Solana         : "<base58 tx signature>"
 *     Hedera         : "<account_id>@<seconds>.<nanos>"
 *     Stellar        : "<64-char hex tx hash>"
 */
function exampleConfirmAuthority(AlgoVoi $av, string $authorityId, string $onChainHandle): ?array
{
    $confirmed = $av->confirmAuthority($authorityId, $onChainHandle);
    if ($confirmed === null) {
        throw new RuntimeException('Confirmation failed');
    }
    echo "[confirm] status = {$confirmed['status']}  (should be 'active')\n";
    return $confirmed;
}

// ---------------------------------------------------------------------------
// Step 3 — Read state any time
// ---------------------------------------------------------------------------

function exampleInspect(AlgoVoi $av, string $authorityId): void
{
    $a = $av->getAuthority($authorityId);
    if ($a === null) {
        echo "[inspect] not found\n";
        return;
    }
    printf(
        "[inspect] status=%s cycles=%d/%d remaining=%d\n",
        $a['status'],
        $a['cycles_pulled'] ?? 0,
        ($a['cycles_pulled'] ?? 0) + ($a['cycles_failed'] ?? 0),
        $a['cap_remaining_minor'] ?? 0
    );
    if (!empty($a['last_error'])) {
        echo "[inspect] last_error = {$a['last_error']}\n";
    }
}

function exampleListActive(AlgoVoi $av): void
{
    $auths = $av->listAuthorities(null, 'active', 50);
    if ($auths === null) {
        echo "[list] failed\n";
        return;
    }
    printf("[list] %d active authorities\n", count($auths));
    foreach ($auths as $a) {
        printf("    %s  chain=%s  cycles=%d\n",
            $a['id'], $a['chain'], $a['cycles_pulled'] ?? 0);
    }
}

// ---------------------------------------------------------------------------
// Step 4 — Lifecycle controls
// ---------------------------------------------------------------------------

function examplePause(AlgoVoi $av, string $authorityId): void { $av->pauseAuthority($authorityId); }

function exampleResume(AlgoVoi $av, string $authorityId): void { $av->resumeAuthority($authorityId); }

function exampleRevoke(AlgoVoi $av, string $authorityId): void
{
    $r = $av->revokeAuthority($authorityId);
    if ($r === null) {
        echo "[revoke] failed\n";
        return;
    }
    echo "[revoke] status = {$r['status']}\n";  // 'revoking' → 'revoked'
}

function exampleManualPull(AlgoVoi $av, string $authorityId, int $amountMinor): void
{
    $r = $av->manualPull($authorityId, $amountMinor, "manual_{$authorityId}_{$amountMinor}");
    if ($r === null) {
        echo "[pull] failed (check per-cycle cap)\n";
        return;
    }
    echo "[pull] accepted; status = " . ($r['status'] ?? 'unknown') . "\n";
}

// ---------------------------------------------------------------------------
// Step 5 — Webhook handler
//
// Tier 2 emits these event types alongside Tier 1's payment.* events.
// verifyWebhook + isRecurringEvent let you fork the handler.
// ---------------------------------------------------------------------------

function exampleWebhookHandler(AlgoVoi $av, string $rawBody, string $signature): array
{
    $payload = $av->verifyWebhook($rawBody, $signature);
    if ($payload === null) {
        return ['status' => 401, 'body' => 'Unauthorized'];
    }

    if (AlgoVoi::isRecurringEvent($payload)) {
        $eventType = $payload['event_type'] ?? '';
        $authorityId = $payload['authority_id'] ?? null;

        switch ($eventType) {
            case 'subscription.charged':
                $txId = $payload['tx_id'] ?? null;
                echo "[webhook] charged: authority=$authorityId tx=$txId\n";
                break;
            case 'subscription.payment_failed':
                $reason = $payload['failure_reason'] ?? null;
                echo "[webhook] failed: authority=$authorityId reason=$reason\n";
                break;
            case 'recurring.authority_revoked':
                echo "[webhook] revoked: authority=$authorityId\n";
                break;
            case 'recurring.authority_expired':
                echo "[webhook] expired: authority=$authorityId\n";
                break;
            default:
                echo "[webhook] $eventType: authority=$authorityId\n";
        }
    } else {
        $orderId = $payload['order_id'] ?? null;
        echo "[webhook] one-shot event for order=$orderId\n";
    }
    return ['status' => 200, 'body' => 'ok'];
}

// ---------------------------------------------------------------------------
// Smoke check (no network calls — just verifies the adapter is wired)
// ---------------------------------------------------------------------------

if (PHP_SAPI === 'cli' && realpath($argv[0]) === __FILE__) {
    echo "Tier 2 chains supported by this adapter:\n";
    $chains = array_keys(AlgoVoi::RECURRING_NETWORKS);
    sort($chains);
    foreach ($chains as $c) echo "  - $c\n";

    echo "\nTier 2 webhook event types:\n";
    $events = array_keys(AlgoVoi::RECURRING_EVENT_TYPES);
    sort($events);
    foreach ($events as $e) echo "  - $e\n";

    echo "\nReady to integrate. Replace the api_key / tenant_id / "
       . "webhook_secret at the top of this file with real values, "
       . "then call exampleCreateAuthority(\$av, ...).\n";
}
