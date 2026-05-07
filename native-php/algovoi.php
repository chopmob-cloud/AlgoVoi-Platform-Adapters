<?php
/**
 * AlgoVoi Native PHP Payment Adapter
 *
 * Single-file drop-in for any PHP application. No framework, no composer, no dependencies.
 *
 * Supports:
 *
 * Tier 1 — one-shot payments
 *   - Hosted checkout (Algorand, VOI, Hedera, Stellar) — redirect to AlgoVoi payment page
 *   - Extension payment (Algorand, VOI) — in-page wallet flow via algosdk
 *   - Webhook verification with HMAC
 *   - SSRF protection on checkout URL fetches
 *   - Cancel-bypass prevention on hosted return
 *
 * Tier 2 — standing-authority recurring (subscriptions, agent-bound auth)
 *   - Create / list / get / revoke / pause / resume / confirm / pull authorities
 *   - Seven chains: Algorand, VOI, Base, Tempo, Solana, Hedera, Stellar
 *   - Customer signs ONE pre-authorisation; AlgoVoi auto-pulls per cycle
 *   - Wallet performs chain-native signing — adapter is stdlib-only HTTP
 *
 * See `Recurr/<chain>/README.md` in this repository for per-chain wallet-side flows.
 *
 * Usage:
 *   require_once 'algovoi.php';
 *   $av = new AlgoVoi([
 *       'api_base'       => 'https://api1.ilovechicken.co.uk',
 *       'api_key'        => 'algv_...',
 *       'tenant_id'      => 'uuid',
 *       'webhook_secret' => 'your_secret',
 *   ]);
 *
 *   // Tier 1 — one-shot
 *   $link = $av->hostedCheckout(10.0, 'USD', 'Order #1', 'algorand_mainnet',
 *                               'https://shop.example/return');
 *
 *   // Tier 2 — recurring
 *   $resp = $av->createRecurringAuthority([
 *       'subscription_id'         => $subId,
 *       'chain'                   => 'algorand_mainnet',
 *       'customer_wallet_address' => 'ABCD...XYZ',
 *       'cap_amount_minor'        => 120_000_000,    // 12 × $10
 *       'cap_period_seconds'      => 365 * 86400,
 *       'per_cycle_amount_minor'  => 10_000_000,
 *   ]);
 *   // Hand $resp['customer_signing_payload'] to your frontend wallet UI.
 *
 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 — see LICENSE for details.
 *
 * Version: 1.2.0
 */

class AlgoVoi
{
    public const VERSION                   = '1.2.0';
    public const MAX_WEBHOOK_BODY_BYTES    = 65536;   // 64 KB
    public const MAX_TOKEN_LEN             = 200;
    public const MAX_TX_ID_LEN             = 200;
    public const MAX_RECURRING_BODY_BYTES  = 16384;   // recurring API responses <4 KB in practice
    public const MAX_UUID_LEN              = 36;     // standard UUID string length

    /**
     * Tier 2 — every v1 chain has a real provider. Map of chain id =>
     * true. Use isRecurringNetwork() to test.
     *
     * 7 mainnets + 7 testnets (matches native-python / native-go).
     */
    public const RECURRING_NETWORKS = [
        'algorand_mainnet' => true, 'algorand_testnet' => true,
        'voi_mainnet'      => true, 'voi_testnet'      => true,
        'base_mainnet'     => true, 'base_sepolia'     => true,
        'tempo_mainnet'    => true, 'tempo_testnet'    => true,
        'solana_mainnet'   => true, 'solana_devnet'    => true,
        'hedera_mainnet'   => true, 'hedera_testnet'   => true,
        'stellar_mainnet'  => true, 'stellar_testnet'  => true,
    ];

    /**
     * Tier 2 webhook event types (in addition to Tier 1's payment.* events).
     * Use isRecurringEvent() to fork your handler.
     */
    public const RECURRING_EVENT_TYPES = [
        'recurring.authority_created'   => true,
        'recurring.authority_activated' => true,
        'recurring.authority_paused'    => true,
        'recurring.authority_resumed'   => true,
        'recurring.authority_revoked'   => true,
        'recurring.authority_expired'   => true,
        'subscription.charged'          => true,
        'subscription.payment_failed'   => true,
    ];

    private string $apiBase;
    private string $apiKey;
    private string $tenantId;
    private string $webhookSecret;

    /**
     * Default Algorand-family node endpoints used by the extension flow.
     * Overridable by subclasses (PHP private constants are immutable —
     * use a protected static array so a child class can swap providers
     * if a node migrates domains).
     */
    protected static array $algod = [
        'algorand-mainnet' => ['url' => 'https://mainnet-api.algonode.cloud', 'asset_id' => 31566704, 'ticker' => 'USDC',  'dec' => 6],
        'voi-mainnet'      => ['url' => 'https://mainnet-api.voi.nodely.io',  'asset_id' => 302190,   'ticker' => 'aUSDC', 'dec' => 6],
    ];

    private const HOSTED_NETWORKS = ['algorand_mainnet', 'voi_mainnet', 'hedera_mainnet', 'stellar_mainnet'];
    private const EXT_NETWORKS    = ['algorand_mainnet', 'voi_mainnet'];

    public function __construct(array $config)
    {
        $this->apiBase       = rtrim($config['api_base'] ?? 'https://api1.ilovechicken.co.uk', '/');
        $this->apiKey        = $config['api_key'] ?? '';
        $this->tenantId      = $config['tenant_id'] ?? '';
        $this->webhookSecret = $config['webhook_secret'] ?? '';
    }

    /** Refuse to make any outbound call over plaintext HTTP. */
    private function isHttps(string $url): bool
    {
        return str_starts_with($url, 'https://');
    }

    /* ────────────────────────────────────────────────────────────────────────
     * Payment Link Creation
     * ──────────────────────────────────────────────────────────────────────── */

    /**
     * Create a payment link via the AlgoVoi API.
     *
     * @param float  $amount      Order total
     * @param string $currency    ISO currency code (e.g. USD, GBP)
     * @param string $label       Order label (e.g. "Order #123")
     * @param string $network     Preferred network (algorand_mainnet, voi_mainnet, hedera_mainnet, stellar_mainnet)
     * @param string $redirectUrl Return URL after hosted checkout (optional)
     * @return array|null         API response or null on failure
     */
    public function createPaymentLink(float $amount, string $currency, string $label, string $network, string $redirectUrl = ''): ?array
    {
        // Defence-in-depth: reject obviously bad amounts before the
        // gateway call. PHP's json_encode would return false for NaN/INF
        // anyway, but failing closed earlier keeps logs clean and avoids
        // wasted round-trips.
        if (!is_finite($amount) || $amount <= 0) {
            return null;
        }

        $payload = [
            'amount'            => round($amount, 2),
            'currency'          => strtoupper($currency),
            'label'             => $label,
            'preferred_network' => $network,
        ];
        if ($redirectUrl !== '') {
            // https-only: checkout tokens or payment-status parameters
            // appended by the gateway must not travel over plaintext.
            // Also blocks SSRF schemes (file://, gopher://, javascript:).
            $scheme = parse_url($redirectUrl, PHP_URL_SCHEME);
            $host   = parse_url($redirectUrl, PHP_URL_HOST);
            if ($scheme !== 'https' || !$host) {
                return null;
            }
            $payload['redirect_url'] = $redirectUrl;
            $payload['expires_in_seconds'] = 3600;
        }

        $resp = $this->post('/v1/payment-links', $payload);
        if (!$resp || empty($resp['checkout_url'])) {
            return null;
        }
        return $resp;
    }

    /**
     * Extract the short token from a checkout URL.
     */
    public function extractToken(string $checkoutUrl): string
    {
        if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $checkoutUrl, $m)) {
            return $m[1];
        }
        return '';
    }

    /* ────────────────────────────────────────────────────────────────────────
     * Hosted Checkout Flow
     * ──────────────────────────────────────────────────────────────────────── */

    /**
     * Start a hosted checkout. Returns the redirect URL or null on failure.
     *
     * @param float  $amount      Order total
     * @param string $currency    ISO currency code
     * @param string $label       Order label
     * @param string $network     Must be one of HOSTED_NETWORKS
     * @param string $redirectUrl URL to return to after payment
     * @return array{checkout_url: string, token: string}|null
     */
    public function hostedCheckout(float $amount, string $currency, string $label, string $network, string $redirectUrl): ?array
    {
        if (!in_array($network, self::HOSTED_NETWORKS, true)) {
            $network = 'algorand_mainnet';
        }

        $link = $this->createPaymentLink($amount, $currency, $label, $network, $redirectUrl);
        if (!$link) return null;

        return [
            'checkout_url' => $link['checkout_url'],
            'token'        => $this->extractToken($link['checkout_url']),
            'chain'        => $link['chain'] ?? 'algorand-mainnet',
            'amount_microunits' => (int)($link['amount_microunits'] ?? 0),
        ];
    }

    /**
     * Verify that a hosted checkout was actually paid before marking an order complete.
     * Call this when the customer returns from the hosted checkout page.
     *
     * @param string $token The checkout token stored when the payment was created
     * @return bool True only if the API confirms payment is complete
     */
    public function verifyHostedReturn(string $token): bool
    {
        if (!$token) return false;
        if (strlen($token) > self::MAX_TOKEN_LEN) return false;
        // Refuse to send the checkout token over plaintext HTTP.
        if (!$this->isHttps($this->apiBase)) return false;

        $ch = curl_init($this->apiBase . '/checkout/' . rawurlencode($token));
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode !== 200) return false;

        $data   = json_decode($response, true) ?? [];
        $status = $data['status'] ?? '';

        return in_array($status, ['paid', 'completed', 'confirmed'], true);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * Extension Payment Flow
     * ──────────────────────────────────────────────────────────────────────── */

    /**
     * Prepare data for the extension (in-page) payment flow.
     * Returns all variables needed to render the JavaScript payment UI.
     *
     * @param float  $amount   Order total
     * @param string $currency ISO currency code
     * @param string $label    Order label
     * @param string $network  Must be one of EXT_NETWORKS
     * @return array|null      Payment data for JS rendering, or null on failure
     */
    public function extensionCheckout(float $amount, string $currency, string $label, string $network): ?array
    {
        if (!in_array($network, self::EXT_NETWORKS, true)) {
            $network = 'algorand_mainnet';
        }

        $link = $this->createPaymentLink($amount, $currency, $label, $network);
        if (!$link) return null;

        $checkoutUrl = $link['checkout_url'];
        $chain       = $link['chain'] ?? 'algorand-mainnet';
        $amountMu    = (int)($link['amount_microunits'] ?? 0);
        $algod       = static::$algod[$chain] ?? static::$algod['algorand-mainnet'];

        // SSRF guard
        $scraped = $this->scrapeCheckout($checkoutUrl);
        if (!$scraped) return null;

        $token = $this->extractToken($checkoutUrl);

        return [
            'token'          => $token,
            'receiver'       => $scraped['receiver'],
            'memo'           => $scraped['memo'],
            'amount_mu'      => $amountMu,
            'asset_id'       => $algod['asset_id'],
            'algod_url'      => $algod['url'],
            'ticker'         => $algod['ticker'],
            'amount_display' => number_format($amountMu / (10 ** $algod['dec']), 2),
            'chain'          => $chain,
            'checkout_url'   => $checkoutUrl,
        ];
    }

    /**
     * Verify an extension payment transaction with the AlgoVoi API.
     *
     * @param string $token The checkout token
     * @param string $txId  The on-chain transaction ID
     * @return array        API response with 'success' key on success
     */
    public function verifyExtensionPayment(string $token, string $txId): array
    {
        // Length-cap BOTH inputs — token was previously only checked
        // for truthiness, allowing arbitrary-length payloads to be
        // URL-encoded into the request path.
        if (!$token || !$txId
                || strlen($token) > self::MAX_TOKEN_LEN
                || strlen($txId)  > self::MAX_TX_ID_LEN) {
            return ['error' => 'Invalid parameters', '_http_code' => 400];
        }
        // Refuse to send the checkout token over plaintext HTTP.
        if (!$this->isHttps($this->apiBase)) {
            return ['error' => 'Insecure api_base scheme', '_http_code' => 400];
        }

        $ch = curl_init($this->apiBase . '/checkout/' . rawurlencode($token) . '/verify');
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode(['tx_id' => $txId]),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $body = json_decode($response, true) ?? [];
        $body['_http_code'] = $httpCode;
        return $body;
    }

    /* ────────────────────────────────────────────────────────────────────────
     * Webhook Handling
     * ──────────────────────────────────────────────────────────────────────── */

    /**
     * Verify and parse an incoming webhook request.
     *
     * @param string $rawBody  The raw POST body
     * @param string $signature The X-AlgoVoi-Signature header value
     * @return array|null       Parsed webhook payload, or null if verification fails
     */
    public function verifyWebhook(string $rawBody, string $signature): ?array
    {
        if (empty($this->webhookSecret)) {
            return null; // Reject if secret not configured
        }
        // Reject empty signatures and oversized bodies before doing the
        // (cheap but unnecessary) HMAC computation.
        if ($signature === '') {
            return null;
        }
        if (strlen($rawBody) > self::MAX_WEBHOOK_BODY_BYTES) {
            return null;
        }

        $expected = base64_encode(hash_hmac('sha256', $rawBody, $this->webhookSecret, true));

        if (!hash_equals($expected, $signature)) {
            return null;
        }

        // Avoid a TypeError when the body is valid JSON but not an
        // object — json_decode returns the scalar (int, string, bool)
        // and our `?array` return type would then throw at the boundary.
        $decoded = json_decode($rawBody, true);
        return is_array($decoded) ? $decoded : null;
    }

    /**
     * Test whether a parsed webhook payload is a Tier 2 (recurring) event.
     *
     * Use this to fork your handler:
     *
     *     $payload = $av->verifyWebhook($rawBody, $signature);
     *     if ($payload === null) { http_response_code(401); exit; }
     *     if (AlgoVoi::isRecurringEvent($payload)) {
     *         handle_recurring($payload);   // subscription.charged, etc.
     *     } else {
     *         handle_one_shot($payload);    // payment.succeeded, etc.
     *     }
     */
    public static function isRecurringEvent(?array $payload): bool
    {
        if ($payload === null) {
            return false;
        }
        $type = $payload['event_type'] ?? $payload['type'] ?? null;
        return is_string($type) && isset(self::RECURRING_EVENT_TYPES[$type]);
    }

    /** Test whether a chain id is a Tier 2 (recurring) network. */
    public static function isRecurringNetwork(string $network): bool
    {
        return isset(self::RECURRING_NETWORKS[$network]);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * Tier 2 — Standing-Authority Recurring Payments
     *
     * Lifecycle:
     *   1. Tenant creates a subscription (POST /v1/subscriptions — out
     *      of scope of this adapter; use the dashboard or call directly).
     *   2. createRecurringAuthority(...) — gateway returns
     *      `customer_signing_payload`, a chain-specific template.
     *   3. Frontend hands the template to the customer's wallet (Pera /
     *      Defly / MetaMask / Phantom / HashPack / Freighter / etc.)
     *      which constructs + signs the on-chain authorisation.
     *   4. confirmAuthority(...) marks status='active' (or AlgoVoi's
     *      hosted widget does it via webhook).
     *   5. AlgoVoi's cycle reaper auto-pulls per cap_period_seconds.
     *      Each pull emits subscription.charged / subscription.payment_failed.
     *   6. revokeAuthority / pauseAuthority / resumeAuthority lifecycle.
     *
     * All methods return the parsed JSON response on success, or null
     * on failure (mirrors the Tier 1 pattern).
     * ──────────────────────────────────────────────────────────────────────── */

    /**
     * Create a Tier 2 standing authority for an existing subscription.
     *
     * Required keys in $req:
     *   - subscription_id          (string UUID)
     *   - chain                    (one of RECURRING_NETWORKS)
     *   - customer_wallet_address  (chain-native; algosdk 58-char base32,
     *                               EVM 0x-hex 42, Solana base58 32-44,
     *                               Hedera 0.0.X, Stellar G-address 56)
     *   - cap_amount_minor         (positive int, atomic units)
     *   - cap_period_seconds       (positive int, >= 86400 == 1 day)
     *   - per_cycle_amount_minor   (positive int, <= cap_amount_minor)
     *
     * Optional:
     *   - asset                    (default 'USDC')
     *   - metadata                 (associative array, forwarded on every webhook)
     *
     * Stellar uses 7-decimal precision for USDC; every other chain uses 6.
     * Pass amounts in chain-native atomic units.
     *
     * @return array|null Server response with 'authority',
     *                    'customer_signing_payload', 'authorisation_url'.
     *                    Hand 'customer_signing_payload' to your frontend
     *                    wallet UI — see Recurr/<chain>/README.md.
     */
    public function createRecurringAuthority(array $req): ?array
    {
        if (!isset($req['chain']) || !self::isRecurringNetwork($req['chain'])) {
            return null;
        }
        $sid = $req['subscription_id'] ?? '';
        if (!is_string($sid) || $sid === '' || strlen($sid) > self::MAX_UUID_LEN) {
            return null;
        }
        $wallet = $req['customer_wallet_address'] ?? '';
        if (!is_string($wallet) || $wallet === '') {
            return null;
        }
        foreach (['cap_amount_minor', 'cap_period_seconds', 'per_cycle_amount_minor'] as $k) {
            if (!isset($req[$k]) || !is_int($req[$k]) || $req[$k] <= 0) {
                return null;
            }
        }
        if ($req['cap_period_seconds'] < 86400) {
            return null;
        }
        if ($req['per_cycle_amount_minor'] > $req['cap_amount_minor']) {
            return null;
        }

        $body = [
            'subscription_id'         => $sid,
            'chain'                   => $req['chain'],
            'customer_wallet_address' => $wallet,
            'cap_amount_minor'        => $req['cap_amount_minor'],
            'cap_period_seconds'      => $req['cap_period_seconds'],
            'per_cycle_amount_minor'  => $req['per_cycle_amount_minor'],
            'asset'                   => strtoupper($req['asset'] ?? 'USDC'),
        ];
        if (isset($req['metadata'])) {
            if (!is_array($req['metadata'])) {
                return null;
            }
            $body['metadata'] = $req['metadata'];
        }
        return $this->requestJson('POST', '/v1/recurring/authorities', $body);
    }

    /**
     * Fetch the current state of a recurring authority by id.
     *
     * Returns the row with status / on_chain_address (once active) /
     * cap_remaining_minor / cycles_pulled / cycles_failed / last_error.
     */
    public function getAuthority(string $authorityId): ?array
    {
        if ($authorityId === '' || strlen($authorityId) > self::MAX_UUID_LEN) {
            return null;
        }
        return $this->requestJson(
            'GET',
            '/v1/recurring/authorities/' . rawurlencode($authorityId)
        );
    }

    /**
     * List recurring authorities for this tenant. Optionally filter by
     * subscription_id or status (pending / active / paused / revoking /
     * revoked / expired).
     *
     * @return array|null List of authority rows (possibly empty), or null on failure.
     */
    public function listAuthorities(
        ?string $subscriptionId = null,
        ?string $status = null,
        int $limit = 50,
        int $offset = 0
    ): ?array {
        if ($limit < 1 || $limit > 200 || $offset < 0) {
            return null;
        }
        $params = ['limit' => (string)$limit, 'offset' => (string)$offset];
        if ($subscriptionId !== null) {
            if (strlen($subscriptionId) > self::MAX_UUID_LEN) {
                return null;
            }
            $params['subscription_id'] = $subscriptionId;
        }
        if ($status !== null) {
            if (strlen($status) > 32 || !preg_match('/^[A-Za-z0-9_]+$/', $status)) {
                return null;
            }
            $params['status'] = $status;
        }
        $path = '/v1/recurring/authorities?' . http_build_query($params);
        $result = $this->requestJson('GET', $path);
        // Gateway returns a JSON array (not an object) — both are valid.
        if (!is_array($result)) {
            return null;
        }
        return $result;
    }

    /**
     * Mark a pending authority active after on-chain landing.
     *
     * `$onChainAddress` format depends on the chain:
     *   Algorand / VOI : "app:<application_id>"
     *   EVM            : "0x<tx_hash>"
     *   Solana         : "<base58 tx signature>"
     *   Hedera         : "<account_id>@<seconds>.<nanos>"
     *   Stellar        : "<64-char hex tx hash>"
     *
     * Most tenants don't need to call this — the AlgoVoi widget does it.
     * Surfaced here for self-hosted wallet UIs.
     */
    public function confirmAuthority(
        string $authorityId,
        string $onChainAddress,
        ?string $firstCycleDueAt = null
    ): ?array {
        if ($authorityId === '' || strlen($authorityId) > self::MAX_UUID_LEN) {
            return null;
        }
        if ($onChainAddress === '' || strlen($onChainAddress) > 200) {
            return null;
        }
        $body = ['on_chain_address' => $onChainAddress];
        if ($firstCycleDueAt !== null) {
            if (strlen($firstCycleDueAt) > 64) {
                return null;
            }
            $body['first_cycle_due_at'] = $firstCycleDueAt;
        }
        return $this->requestJson(
            'POST',
            '/v1/recurring/authorities/' . rawurlencode($authorityId) . '/confirm',
            $body
        );
    }

    /**
     * Revoke an active authority. Gateway constructs the chain-specific
     * revocation transaction; the customer's wallet signs it. Authority
     * transitions to 'revoking' until on-chain landing, then 'revoked'.
     */
    public function revokeAuthority(string $authorityId): ?array
    {
        if ($authorityId === '' || strlen($authorityId) > self::MAX_UUID_LEN) {
            return null;
        }
        return $this->requestJson(
            'POST',
            '/v1/recurring/authorities/' . rawurlencode($authorityId) . '/revoke',
            []
        );
    }

    /**
     * Pause an active authority — no on-chain action. Stops cycle pulls
     * until resumeAuthority(...) is called.
     */
    public function pauseAuthority(string $authorityId): ?array
    {
        if ($authorityId === '' || strlen($authorityId) > self::MAX_UUID_LEN) {
            return null;
        }
        return $this->requestJson(
            'POST',
            '/v1/recurring/authorities/' . rawurlencode($authorityId) . '/pause',
            []
        );
    }

    /**
     * Resume a paused authority. Pass `$nextCycleDueAt` (ISO8601) to
     * delay the first post-resume pull; otherwise pulls resume on the
     * existing schedule.
     */
    public function resumeAuthority(string $authorityId, ?string $nextCycleDueAt = null): ?array
    {
        if ($authorityId === '' || strlen($authorityId) > self::MAX_UUID_LEN) {
            return null;
        }
        $body = [];
        if ($nextCycleDueAt !== null) {
            if (strlen($nextCycleDueAt) > 64) {
                return null;
            }
            $body['next_cycle_due_at'] = $nextCycleDueAt;
        }
        return $this->requestJson(
            'POST',
            '/v1/recurring/authorities/' . rawurlencode($authorityId) . '/resume',
            $body
        );
    }

    /**
     * Manually trigger a pull (e.g. catch-up after error escalation,
     * prorated mid-cycle billing). Most pulls fire automatically via
     * the cycle reaper — only use this for proration or dunning catch-ups.
     *
     * `$amountMinor` must be <= per_cycle_amount_minor of the authority.
     */
    public function manualPull(
        string $authorityId,
        int $amountMinor,
        ?string $idempotencyKey = null
    ): ?array {
        if ($authorityId === '' || strlen($authorityId) > self::MAX_UUID_LEN) {
            return null;
        }
        if ($amountMinor <= 0) {
            return null;
        }
        $body = ['authority_id' => $authorityId, 'amount_minor' => $amountMinor];
        if ($idempotencyKey !== null) {
            if (strlen($idempotencyKey) > 128) {
                return null;
            }
            $body['idempotency_key'] = $idempotencyKey;
        }
        return $this->requestJson('POST', '/v1/recurring/pulls', $body);
    }

    /* ────────────────────────────────────────────────────────────────────────
     * HTML Rendering Helpers
     * ──────────────────────────────────────────────────────────────────────── */

    /**
     * Render chain selector radio buttons.
     *
     * @param string $fieldName  Form field name
     * @param string $type       'hosted' (3 chains) or 'extension' (2 chains)
     * @return string            HTML
     */
    public static function renderChainSelector(string $fieldName, string $type = 'hosted'): string
    {
        $chains = [
            ['value' => 'algorand_mainnet', 'label' => 'Algorand', 'ticker' => 'USDC',  'colour' => '#3b82f6'],
            ['value' => 'voi_mainnet',      'label' => 'VOI',      'ticker' => 'aUSDC', 'colour' => '#8b5cf6'],
        ];
        if ($type === 'hosted') {
            $chains[] = ['value' => 'hedera_mainnet',  'label' => 'Hedera',  'ticker' => 'USDC', 'colour' => '#00a9a5'];
            $chains[] = ['value' => 'stellar_mainnet', 'label' => 'Stellar', 'ticker' => 'USDC', 'colour' => '#7C63D0'];
        }

        $html = '<div style="margin:.5rem 0;font-size:12px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Select network</div>';
        $html .= '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:.5rem;">';
        foreach ($chains as $i => $c) {
            $checked = $i === 0 ? ' checked' : '';
            $html .= '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">';
            $html .= '<input type="radio" name="' . htmlspecialchars($fieldName) . '" value="' . htmlspecialchars($c['value']) . '"' . $checked . ' style="accent-color:' . $c['colour'] . ';">';
            $html .= ' ' . htmlspecialchars($c['label']) . ' &mdash; ' . htmlspecialchars($c['ticker']);
            $html .= '</label>';
        }
        $html .= '</div>';
        return $html;
    }

    /**
     * Render the extension payment JavaScript UI.
     *
     * @param array  $paymentData Return value from extensionCheckout()
     * @param string $verifyUrl   Your server endpoint that calls verifyExtensionPayment()
     * @param string $successUrl  URL to redirect to after successful payment
     * @return string             HTML + JS block
     */
    public static function renderExtensionPaymentUI(array $paymentData, string $verifyUrl, string $successUrl): string
    {
        $sa = htmlspecialchars($paymentData['amount_display'] . ' ' . $paymentData['ticker']);
        $sc = htmlspecialchars(str_contains($paymentData['chain'], 'voi') ? 'VOI' : 'Algorand');
        $sco = htmlspecialchars($paymentData['checkout_url']);
        $jr = json_encode($paymentData['receiver']);
        $jm = json_encode($paymentData['memo']);
        $ja = json_encode($paymentData['algod_url']);
        $jv = json_encode($verifyUrl);
        $js = json_encode($successUrl);

        return <<<HTML
<div id="av-ext-pay" style="max-width:520px;margin:2rem auto;padding:1.5rem 1.75rem;background:#1e2130;border:1px solid #2a2d3a;border-radius:12px;color:#f1f2f6;font-family:system-ui,sans-serif;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#6b7280;margin-bottom:.85rem;">
    <span style="color:#3b82f6;">AlgoVoi</span> &middot; {$sc} Extension Payment
  </div>
  <p style="margin:0 0 1.25rem;color:#9ca3af;font-size:.9rem;line-height:1.6;">
    Send <strong style="color:#10b981;">{$sa}</strong> on <strong style="color:#f1f2f6;">{$sc}</strong> via the AlgoVoi browser extension.
  </p>
  <div id="av-no-ext" style="display:none;margin-bottom:1rem;padding:.75rem 1rem;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;font-size:.85rem;color:#ef4444;">
    AlgoVoi extension not detected. <a href="{$sco}" target="_blank" rel="noopener" style="color:#3b82f6;">Pay on hosted checkout &rarr;</a>
  </div>
  <div id="av-msg" style="display:none;margin-bottom:.85rem;padding:.65rem .9rem;border-radius:8px;font-size:.85rem;"></div>
  <button id="av-pay-btn" onclick="avPayWithExtension()"
    style="display:inline-flex;align-items:center;gap:.5rem;padding:.8rem 1.6rem;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-size:.95rem;font-weight:600;cursor:pointer;">
    &#9889; Pay {$sa} via Extension
  </button>
  <p style="margin:.85rem 0 0;font-size:.75rem;color:#6b7280;">
    No extension? <a href="{$sco}" target="_blank" rel="noopener" style="color:#3b82f6;">Pay on hosted checkout</a> instead.
  </p>
</div>
<script src="https://cdn.jsdelivr.net/npm/algosdk@2/dist/browser/algosdk.min.js"></script>
<script>
(function(){
  var AV={receiver:{$jr},memo:{$jm},microunits:{$paymentData['amount_mu']},assetId:{$paymentData['asset_id']},algodUrl:{$ja},verifyUrl:{$jv},successUrl:{$js}};
  function showMsg(h,t){var e=document.getElementById('av-msg');e.innerHTML=h;e.style.display='block';e.style.background=t==='ok'?'rgba(16,185,129,.1)':'rgba(239,68,68,.1)';e.style.border=t==='ok'?'1px solid rgba(16,185,129,.3)':'1px solid rgba(239,68,68,.3)';e.style.color=t==='ok'?'#10b981':'#ef4444';}
  function setBtn(t,d){var b=document.getElementById('av-pay-btn');if(!b)return;b.textContent=t;b.disabled=!!d;b.style.opacity=d?'.6':'1';}
  function u8b64(a){var s='';for(var i=0;i<a.length;i++)s+=String.fromCharCode(a[i]);return btoa(s);}
  window.avPayWithExtension=async function(){
    try{
      setBtn('Connecting\u2026',true);
      if(!window.algorand||!window.algorand.isAlgoVoi){document.getElementById('av-no-ext').style.display='block';document.getElementById('av-pay-btn').style.display='none';return;}
      setBtn('Fetching params\u2026',true);
      var algodClient=new algosdk.Algodv2('',AV.algodUrl,'');
      var sp=await algodClient.getTransactionParams().do();
      setBtn('Connecting wallet\u2026',true);
      var er=await window.algorand.enable({genesisHash:sp.genesisHash});
      if(!er.accounts||!er.accounts.length)throw new Error('No accounts returned.');
      var sender=er.accounts[0];
      setBtn('Building tx\u2026',true);
      var nb=new TextEncoder().encode(AV.memo);
      var txn=algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({from:sender,to:AV.receiver,assetIndex:AV.assetId,amount:AV.microunits,note:nb,suggestedParams:sp});
      setBtn('Sign & send\u2026',true);
      var res=await window.algorand.signAndSendTransactions({txns:[{txn:u8b64(txn.toByte())}]});
      if(!res.stxns||!res.stxns[0])throw new Error('No signed transaction returned.');
      var stxnBytes=Uint8Array.from(atob(res.stxns[0]),function(c){return c.charCodeAt(0);});
      setBtn('Submitting\u2026',true);
      var submitResp=await fetch(AV.algodUrl+'/v2/transactions',{method:'POST',headers:{'Content-Type':'application/x-binary'},body:stxnBytes});
      var submitData=await submitResp.json();
      if(!submitResp.ok)throw new Error('Algod submission failed: '+(submitData.message||submitResp.status));
      var txId=submitData.txId;
      if(!txId)throw new Error('No txId in response.');
      setBtn('Waiting for confirmation\u2026',true);
      var confirmed=0;
      for(var a=0;a<20;a++){await new Promise(function(r){setTimeout(r,3000);});var pr=await fetch(AV.algodUrl+'/v2/transactions/pending/'+encodeURIComponent(txId));if(pr.status===404){confirmed=1;break;}var pd=await pr.json();if(pd['confirmed-round']&&pd['confirmed-round']>0){confirmed=pd['confirmed-round'];break;}if(pd['pool-error']&&pd['pool-error'].length>0)throw new Error('Transaction rejected: '+pd['pool-error']);}
      if(!confirmed)throw new Error('Transaction not confirmed after timeout. TX: '+txId);
      await new Promise(function(r){setTimeout(r,4000);});
      setBtn('Verifying\u2026',true);
      var vr=await fetch(AV.verifyUrl,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tx_id:txId})});
      var vd=await vr.json();
      if(vr.ok&&vd.success){showMsg('\u2713 Payment verified! Redirecting\u2026','ok');setBtn('Paid \u2713',true);setTimeout(function(){location=AV.successUrl;},2000);}
      else{throw new Error(vd.detail||vd.error||'Verification failed.');}
    }catch(err){showMsg('&#9888; '+err.message,'err');setBtn('\u26a1 Retry',false);}
  };
  window.addEventListener('load',function(){setTimeout(function(){if(!window.algorand||!window.algorand.isAlgoVoi)document.getElementById('av-no-ext').style.display='block';},700);});
})();
</script>
HTML;
    }

    /* ────────────────────────────────────────────────────────────────────────
     * Internal Helpers
     * ──────────────────────────────────────────────────────────────────────── */

    private function post(string $path, array $data): ?array
    {
        // Refuse to send the API key over plaintext HTTP.
        // This is the highest-impact scheme guard — Authorization: Bearer
        // and X-Tenant-Id are sent on every payment-link creation.
        if (!$this->isHttps($this->apiBase)) {
            return null;
        }

        $ch = curl_init($this->apiBase . $path);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode($data),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $this->apiKey,
                'X-Tenant-Id: ' . $this->tenantId,
            ],
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode < 200 || $httpCode >= 300) return null;

        return json_decode($response, true);
    }

    /**
     * Generic JSON HTTPS request to the AlgoVoi API. Used by Tier 2
     * methods that need GET (list/get) on top of POST.
     *
     * Returns parsed JSON on 2xx. Returns null on any non-2xx, network
     * error, JSON-decode error, or response > MAX_RECURRING_BODY_BYTES
     * — mirrors post()'s failure mode so Tier 2 methods compose with the
     * same caller-side null check.
     *
     * Hookable via the `algovoiHttpHandler` callable for unit tests
     * (when set, replaces the curl path entirely — used by recurring_test.php).
     */
    private function requestJson(string $method, string $path, ?array $data = null): ?array
    {
        if (!in_array($method, ['GET', 'POST', 'DELETE'], true)) {
            return null;
        }
        if (!$this->isHttps($this->apiBase)) {
            return null;
        }

        // Test hook — when set, bypass curl. Allows mocked round-trip
        // tests without spinning up a real HTTPS server.
        if (isset($this->httpHandler) && is_callable($this->httpHandler)) {
            $body = $data === null ? null : json_encode($data);
            return ($this->httpHandler)($method, $this->apiBase . $path, $body, [
                'Authorization: Bearer ' . $this->apiKey,
                'X-Tenant-Id: ' . $this->tenantId,
                'Content-Type: application/json',
            ]);
        }

        $ch = curl_init($this->apiBase . $path);
        $opts = [
            CURLOPT_CUSTOMREQUEST  => $method,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_HTTPHEADER     => [
                'Authorization: Bearer ' . $this->apiKey,
                'X-Tenant-Id: ' . $this->tenantId,
            ],
        ];
        if ($data !== null) {
            $opts[CURLOPT_POSTFIELDS] = json_encode($data);
            $opts[CURLOPT_HTTPHEADER][] = 'Content-Type: application/json';
        }
        curl_setopt_array($ch, $opts);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($response === false || $httpCode < 200 || $httpCode >= 300) {
            return null;
        }
        if (strlen((string)$response) > self::MAX_RECURRING_BODY_BYTES) {
            return null;
        }
        $decoded = json_decode((string)$response, true);
        if (!is_array($decoded)) {
            return null;
        }
        return $decoded;
    }

    /**
     * Test hook — set this callable to bypass curl in unit tests.
     * The callable receives ($method, $url, $bodyJsonOrNull, $headers)
     * and must return either an array (success) or null (failure).
     *
     * @var callable|null
     */
    public $httpHandler = null;

    private function scrapeCheckout(string $checkoutUrl): ?array
    {
        // Refuse to scrape over plaintext HTTP.
        if (!$this->isHttps($checkoutUrl)) {
            return null;
        }

        // SSRF guard: host AND port must match API base. Comparing only
        // hostnames lets a non-standard-port service on the same host
        // slip through if the legitimate API runs on a different port.
        $apiHost      = parse_url($this->apiBase, PHP_URL_HOST);
        $apiPort      = parse_url($this->apiBase, PHP_URL_PORT);
        $checkoutHost = parse_url($checkoutUrl, PHP_URL_HOST);
        $checkoutPort = parse_url($checkoutUrl, PHP_URL_PORT);
        if (!$apiHost || $checkoutHost !== $apiHost || $apiPort !== $checkoutPort) {
            return null;
        }

        $ch = curl_init($checkoutUrl);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);
        $html = curl_exec($ch);
        curl_close($ch);

        $receiver = $memo = '';
        if ($html) {
            if (preg_match('/<div[^>]+id=["\']addr["\'][^>]*>([A-Z2-7]{58})</', $html, $m)) {
                $receiver = $m[1];
            }
            if (preg_match('/<div[^>]+id=["\']memo["\'][^>]*>(algovoi:[^<]+)</', $html, $m)) {
                $memo = trim($m[1]);
            }
        }

        if (!$receiver || !$memo) return null;

        return ['receiver' => $receiver, 'memo' => $memo];
    }
}
