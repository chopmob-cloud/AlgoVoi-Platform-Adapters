<?php
/**
 * Tier 2 recurring tests for native-php (no PHPUnit dependency).
 *
 * Run with:
 *   php recurring_test.php
 *
 * Exits 0 on all-pass, 1 on any failure. Mirrors the test surface in
 * native-go's recurring_test.go and native-python's mocked round-trip
 * suite — same coverage, same shape.
 */

declare(strict_types=1);

require_once __DIR__ . '/algovoi.php';

// ---------------------------------------------------------------------------
// Tiny test runner
// ---------------------------------------------------------------------------

$failures = [];

/** @param callable(): void $fn */
function it(string $name, callable $fn): void
{
    global $failures;
    try {
        $fn();
        echo "  PASS  $name\n";
    } catch (Throwable $e) {
        $failures[] = "$name: " . $e->getMessage();
        echo "  FAIL  $name — " . $e->getMessage() . "\n";
    }
}

function assertTrue(bool $v, string $msg = ''): void
{
    if (!$v) throw new RuntimeException($msg ?: 'assertion failed');
}

function assertEq($want, $got, string $msg = ''): void
{
    if ($want !== $got) {
        $w = is_scalar($want) ? (string)$want : json_encode($want);
        $g = is_scalar($got) ? (string)$got : json_encode($got);
        throw new RuntimeException(($msg ?: 'eq') . ": want $w, got $g");
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient(): AlgoVoi
{
    return new AlgoVoi([
        'api_base'       => 'https://api.example.com',
        'api_key'        => 'algv_k',
        'tenant_id'      => 't-uuid',
        'webhook_secret' => 'whsec_test',
    ]);
}

/**
 * Mock HTTP handler that captures the request and returns a canned response.
 *
 * @param array{response: array|null, captured?: array} $state
 */
function mockHandler(array &$state): callable
{
    return function (string $method, string $url, ?string $body, array $headers) use (&$state): ?array {
        $state['captured'] = [
            'method'  => $method,
            'url'     => $url,
            'body'    => $body === null ? null : json_decode($body, true),
            'headers' => $headers,
        ];
        return $state['response'];
    };
}

// ---------------------------------------------------------------------------
// Constants + helpers
// ---------------------------------------------------------------------------

echo "\n[constants + helpers]\n";

it('RECURRING_NETWORKS covers 7 mainnets + 7 testnets', function () {
    $expect = [
        'algorand_mainnet', 'algorand_testnet',
        'voi_mainnet', 'voi_testnet',
        'base_mainnet', 'base_sepolia',
        'tempo_mainnet', 'tempo_testnet',
        'solana_mainnet', 'solana_devnet',
        'hedera_mainnet', 'hedera_testnet',
        'stellar_mainnet', 'stellar_testnet',
    ];
    assertEq(14, count(AlgoVoi::RECURRING_NETWORKS));
    foreach ($expect as $n) {
        assertTrue(AlgoVoi::isRecurringNetwork($n), "$n should be recurring");
    }
});

it('RECURRING_NETWORKS rejects ethereum / unknown chains', function () {
    assertEq(false, AlgoVoi::isRecurringNetwork('ethereum_mainnet'));
    assertEq(false, AlgoVoi::isRecurringNetwork('polygon_mainnet'));
    assertEq(false, AlgoVoi::isRecurringNetwork(''));
});

it('RECURRING_EVENT_TYPES has all 8', function () {
    assertEq(8, count(AlgoVoi::RECURRING_EVENT_TYPES));
    foreach (
        [
            'recurring.authority_created', 'recurring.authority_activated',
            'recurring.authority_paused', 'recurring.authority_resumed',
            'recurring.authority_revoked', 'recurring.authority_expired',
            'subscription.charged', 'subscription.payment_failed',
        ] as $e
    ) {
        assertTrue(isset(AlgoVoi::RECURRING_EVENT_TYPES[$e]), "$e missing");
    }
});

it('isRecurringEvent classifies correctly', function () {
    assertEq(true, AlgoVoi::isRecurringEvent(['event_type' => 'subscription.charged']));
    assertEq(true, AlgoVoi::isRecurringEvent(['type' => 'recurring.authority_revoked']));
    assertEq(false, AlgoVoi::isRecurringEvent(['event_type' => 'payment.succeeded']));
    assertEq(false, AlgoVoi::isRecurringEvent([]));
    assertEq(false, AlgoVoi::isRecurringEvent(null));
    assertEq(false, AlgoVoi::isRecurringEvent(['event_type' => 12345]));
});

// ---------------------------------------------------------------------------
// Input validation — must short-circuit BEFORE the wire
// ---------------------------------------------------------------------------

echo "\n[input validation]\n";

it('createRecurringAuthority rejects unknown chain', function () {
    $av = makeClient();
    $called = false;
    $av->httpHandler = function () use (&$called) { $called = true; return null; };
    $r = $av->createRecurringAuthority([
        'subscription_id'         => 'sub',
        'chain'                   => 'ethereum_mainnet',
        'customer_wallet_address' => 'X',
        'cap_amount_minor'        => 100,
        'cap_period_seconds'      => 86400,
        'per_cycle_amount_minor'  => 10,
    ]);
    assertEq(null, $r);
    assertEq(false, $called, 'must not call HTTP');
});

it('createRecurringAuthority rejects empty subscription_id', function () {
    $av = makeClient();
    $called = false;
    $av->httpHandler = function () use (&$called) { $called = true; return null; };
    $r = $av->createRecurringAuthority([
        'subscription_id'         => '',
        'chain'                   => 'algorand_mainnet',
        'customer_wallet_address' => 'X',
        'cap_amount_minor'        => 100,
        'cap_period_seconds'      => 86400,
        'per_cycle_amount_minor'  => 10,
    ]);
    assertEq(null, $r);
    assertEq(false, $called);
});

it('createRecurringAuthority rejects period < 1 day', function () {
    $av = makeClient();
    $called = false;
    $av->httpHandler = function () use (&$called) { $called = true; return null; };
    $r = $av->createRecurringAuthority([
        'subscription_id'         => 'sub',
        'chain'                   => 'algorand_mainnet',
        'customer_wallet_address' => 'X',
        'cap_amount_minor'        => 100,
        'cap_period_seconds'      => 3600,  // < 1 day
        'per_cycle_amount_minor'  => 10,
    ]);
    assertEq(null, $r);
    assertEq(false, $called);
});

it('createRecurringAuthority rejects per_cycle > cap', function () {
    $av = makeClient();
    $called = false;
    $av->httpHandler = function () use (&$called) { $called = true; return null; };
    $r = $av->createRecurringAuthority([
        'subscription_id'         => 'sub',
        'chain'                   => 'base_mainnet',
        'customer_wallet_address' => '0xX',
        'cap_amount_minor'        => 10,
        'cap_period_seconds'      => 86400 * 30,
        'per_cycle_amount_minor'  => 100,
    ]);
    assertEq(null, $r);
    assertEq(false, $called);
});

it('getAuthority rejects empty / oversize id', function () {
    $av = makeClient();
    assertEq(null, $av->getAuthority(''));
    assertEq(null, $av->getAuthority(str_repeat('a', 100)));
});

it('listAuthorities rejects oversize limit and bad status', function () {
    $av = makeClient();
    assertEq(null, $av->listAuthorities(null, null, 500));     // limit > 200
    assertEq(null, $av->listAuthorities(null, 'bad-status!')); // non-alnum
    assertEq(null, $av->listAuthorities(null, null, 50, -1));  // negative offset
});

it('manualPull rejects bad inputs', function () {
    $av = makeClient();
    assertEq(null, $av->manualPull('', 10));      // empty id
    assertEq(null, $av->manualPull('id', -1));    // non-positive amount
    assertEq(null, $av->manualPull('id', 0));     // zero amount
});

it('plaintext HTTP refused (no httpHandler hook)', function () {
    $av = new AlgoVoi([
        'api_base'       => 'http://example.com',  // http, not https
        'api_key'        => 'k',
        'tenant_id'      => 't',
        'webhook_secret' => 's',
    ]);
    // Without a hook the curl path runs; isHttps() check should refuse.
    assertEq(null, $av->getAuthority('a1'));
    assertEq(null, $av->createRecurringAuthority([
        'subscription_id'         => 'sub',
        'chain'                   => 'algorand_mainnet',
        'customer_wallet_address' => 'X',
        'cap_amount_minor'        => 100,
        'cap_period_seconds'      => 86400 * 30,
        'per_cycle_amount_minor'  => 10,
    ]));
});

// ---------------------------------------------------------------------------
// Mocked HTTP round-trips
// ---------------------------------------------------------------------------

echo "\n[mocked HTTP round-trips]\n";

it('createRecurringAuthority POSTs correct URL + headers + body', function () {
    $av = makeClient();
    $state = ['response' => [
        'authority' => [
            'id' => 'auth-uuid',
            'tenant_id' => 't-uuid',
            'subscription_id' => 'sub-uuid',
            'chain' => 'algorand_mainnet',
            'customer_wallet_address' => 'X',
            'cap_amount_minor' => 120000000,
            'cap_period_seconds' => 31536000,
            'per_cycle_amount_minor' => 10000000,
            'asset' => 'USDC',
            'status' => 'pending',
            'cap_remaining_minor' => 120000000,
            'cycles_pulled' => 0,
            'cycles_failed' => 0,
            'created_at' => '2026-05-07T00:00:00Z',
        ],
        'customer_signing_payload' => [
            'version' => 'algorand_spending_cap_vault_v1',
            'actions' => [['id' => 'deploy_vault']],
        ],
        'authorisation_url' => null,
    ]];
    $av->httpHandler = mockHandler($state);

    $resp = $av->createRecurringAuthority([
        'subscription_id'         => 'sub-uuid',
        'chain'                   => 'algorand_mainnet',
        'customer_wallet_address' => 'X',
        'cap_amount_minor'        => 120000000,
        'cap_period_seconds'      => 365 * 86400,
        'per_cycle_amount_minor'  => 10000000,
    ]);

    assertTrue($resp !== null, 'response not null');
    assertEq('auth-uuid', $resp['authority']['id']);
    assertEq('pending', $resp['authority']['status']);
    assertEq('algorand_spending_cap_vault_v1', $resp['customer_signing_payload']['version']);

    $cap = $state['captured'];
    assertEq('POST', $cap['method']);
    assertEq('https://api.example.com/v1/recurring/authorities', $cap['url']);
    assertEq('algorand_mainnet', $cap['body']['chain']);
    assertEq(120000000, $cap['body']['cap_amount_minor']);
    assertEq('USDC', $cap['body']['asset'], 'asset default applied');

    // Auth headers present
    $authFound = false; $tenantFound = false;
    foreach ($cap['headers'] as $h) {
        if (str_starts_with($h, 'Authorization: Bearer algv_k')) $authFound = true;
        if (str_starts_with($h, 'X-Tenant-Id: t-uuid'))            $tenantFound = true;
    }
    assertTrue($authFound, 'Authorization header missing');
    assertTrue($tenantFound, 'X-Tenant-Id header missing');
});

it('listAuthorities GETs with query string', function () {
    $av = makeClient();
    $state = ['response' => [
        ['id' => 'a1', 'status' => 'active', 'chain' => 'base_mainnet', 'cycles_pulled' => 3],
    ]];
    $av->httpHandler = mockHandler($state);

    $list = $av->listAuthorities(null, 'active', 10);
    assertTrue($list !== null);
    assertEq(1, count($list));
    assertEq('a1', $list[0]['id']);

    $cap = $state['captured'];
    assertEq('GET', $cap['method']);
    assertTrue(str_contains($cap['url'], 'limit=10'), 'limit in query');
    assertTrue(str_contains($cap['url'], 'status=active'), 'status in query');
    assertEq(null, $cap['body'], 'GET should not send body');
});

it('getAuthority GETs /v1/recurring/authorities/{id}', function () {
    $av = makeClient();
    $state = ['response' => [
        'id' => 'a1', 'status' => 'active', 'cap_remaining_minor' => 110_000_000,
    ]];
    $av->httpHandler = mockHandler($state);

    $a = $av->getAuthority('a1');
    assertTrue($a !== null);
    assertEq('active', $a['status']);
    assertEq(110_000_000, $a['cap_remaining_minor']);
    assertEq('GET', $state['captured']['method']);
    assertEq('https://api.example.com/v1/recurring/authorities/a1', $state['captured']['url']);
});

it('revokeAuthority POSTs to /revoke', function () {
    $av = makeClient();
    $state = ['response' => ['id' => 'a1', 'status' => 'revoking']];
    $av->httpHandler = mockHandler($state);

    $r = $av->revokeAuthority('a1');
    assertEq('revoking', $r['status']);
    assertTrue(str_ends_with($state['captured']['url'], '/revoke'));
    assertEq('POST', $state['captured']['method']);
});

it('confirmAuthority forwards optional first_cycle_due_at', function () {
    $av = makeClient();
    $state = ['response' => ['id' => 'a1', 'status' => 'active']];
    $av->httpHandler = mockHandler($state);

    $av->confirmAuthority('a1', 'app:12345', '2026-06-07T00:00:00Z');
    $body = $state['captured']['body'];
    assertEq('app:12345', $body['on_chain_address']);
    assertEq('2026-06-07T00:00:00Z', $body['first_cycle_due_at']);
});

it('null response from handler returns null (mirror non-2xx)', function () {
    $av = makeClient();
    $av->httpHandler = function () { return null; };
    assertEq(null, $av->getAuthority('a1'));
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

echo "\n";
if (count($failures) > 0) {
    echo count($failures) . " FAILED\n";
    foreach ($failures as $f) echo "  - $f\n";
    exit(1);
}
echo "ALL TESTS PASS\n";
exit(0);
