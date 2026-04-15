<?php
/**
 * Plugin Name:          AlgoVoi for Easy Digital Downloads
 * Plugin URI:           https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Description:          Accept USDC stablecoin payments on Algorand, VOI (aUSDC), Hedera, and Stellar in Easy Digital Downloads. Non-custodial — funds settle to the merchant's wallet. Supports digital downloads, license keys, and EDD Software Licensing.
 * Version:              1.0.0
 * Requires at least:    6.4
 * Requires PHP:         8.0
 * Requires Plugins:     easy-digital-downloads
 * EDD requires at least: 3.2
 * EDD tested up to:     3.3.8
 * Author:               AlgoVoi
 * Author URI:           https://api1.ilovechicken.co.uk
 * License:              BUSL-1.1
 * License URI:          https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/blob/master/LICENSE
 * Text Domain:          algovoi-edd
 *
 * Licensed under the Business Source License 1.1 — see LICENSE for details.
 */
if (!defined('ABSPATH')) exit;

/* ──────────────────────────────────────────────────────────────────────────
 * Register the gateway
 * ──────────────────────────────────────────────────────────────────────── */

add_filter('edd_payment_gateways', function ($gateways) {
    $gateways['algovoi'] = [
        'admin_label'    => 'AlgoVoi (Crypto)',
        'checkout_label' => __('Pay with Crypto (Algorand / VOI / Hedera / Stellar)', 'algovoi-edd'),
        'supports'       => ['buy_now'],
    ];
    return $gateways;
});

/* Non-card gateway — suppress the credit-card form on checkout. */
add_action('edd_algovoi_cc_form', '__return_false');

/* ──────────────────────────────────────────────────────────────────────────
 * Settings page (Downloads → Settings → Payments → AlgoVoi)
 * ──────────────────────────────────────────────────────────────────────── */

add_filter('edd_settings_sections_gateways', function ($sections) {
    $sections['algovoi'] = __('AlgoVoi', 'algovoi-edd');
    return $sections;
});

add_filter('edd_settings_gateways', function ($settings) {
    $settings['algovoi'] = [
        [
            'id'   => 'algovoi_header',
            'name' => '<strong>' . __('AlgoVoi Settings', 'algovoi-edd') . '</strong>',
            'type' => 'header',
        ],
        [
            'id'   => 'algovoi_api_base',
            'name' => __('API Base URL', 'algovoi-edd'),
            'desc' => __('Default: https://api1.ilovechicken.co.uk', 'algovoi-edd'),
            'type' => 'text',
            'std'  => 'https://api1.ilovechicken.co.uk',
        ],
        [
            'id'   => 'algovoi_api_key',
            'name' => __('API Key', 'algovoi-edd'),
            'desc' => __('Your AlgoVoi API key (algv_...)', 'algovoi-edd'),
            'type' => 'password',
        ],
        [
            'id'   => 'algovoi_tenant_id',
            'name' => __('Tenant ID', 'algovoi-edd'),
            'type' => 'text',
        ],
        [
            'id'   => 'algovoi_webhook_secret',
            'name' => __('Webhook Secret', 'algovoi-edd'),
            'desc' => __('SECURITY: if empty, every webhook is rejected.', 'algovoi-edd'),
            'type' => 'password',
        ],
        [
            'id'      => 'algovoi_default_network',
            'name'    => __('Default network', 'algovoi-edd'),
            'type'    => 'select',
            'std'     => 'algorand_mainnet',
            'options' => [
                'algorand_mainnet' => __('Algorand (USDC)', 'algovoi-edd'),
                'voi_mainnet'      => __('VOI (aUSDC)', 'algovoi-edd'),
                'hedera_mainnet'   => __('Hedera (USDC)', 'algovoi-edd'),
                'stellar_mainnet'  => __('Stellar (USDC)', 'algovoi-edd'),
            ],
        ],
    ];
    return $settings;
});

/* ──────────────────────────────────────────────────────────────────────────
 * Process the payment — redirect to AlgoVoi hosted checkout
 * ──────────────────────────────────────────────────────────────────────── */

add_action('edd_gateway_algovoi', function ($purchase_data) {
    $api_base = rtrim(edd_get_option('algovoi_api_base', 'https://api1.ilovechicken.co.uk'), '/');
    $api_key  = edd_get_option('algovoi_api_key', '');
    $tenant   = edd_get_option('algovoi_tenant_id', '');
    $network  = edd_get_option('algovoi_default_network', 'algorand_mainnet');

    if (empty($api_key) || empty($tenant)) {
        edd_set_error('algovoi_not_configured', __('AlgoVoi is not fully configured.', 'algovoi-edd'));
        edd_send_back_to_checkout(['payment-mode' => 'algovoi']);
        return;
    }
    if (!algovoi_edd_is_https($api_base)) {
        edd_set_error('algovoi_insecure', __('AlgoVoi API base must use https://', 'algovoi-edd'));
        edd_send_back_to_checkout(['payment-mode' => 'algovoi']);
        return;
    }

    $amount = (float) $purchase_data['price'];
    if (!is_finite($amount) || $amount <= 0) {
        edd_set_error('algovoi_bad_amount', __('Invalid order amount.', 'algovoi-edd'));
        edd_send_back_to_checkout(['payment-mode' => 'algovoi']);
        return;
    }

    $allowed_networks = ['algorand_mainnet', 'voi_mainnet', 'hedera_mainnet', 'stellar_mainnet'];
    if (!in_array($network, $allowed_networks, true)) {
        $network = 'algorand_mainnet';
    }

    // Create the EDD payment in pending state BEFORE redirecting — gives us
    // an ID to store the AlgoVoi token against, and matches EDD's gateway
    // contract.
    $payment_data = [
        'price'        => $amount,
        'date'         => $purchase_data['date'],
        'user_email'   => $purchase_data['user_email'],
        'purchase_key' => $purchase_data['purchase_key'],
        'currency'     => edd_get_currency(),
        'downloads'    => $purchase_data['downloads'],
        'user_info'    => $purchase_data['user_info'],
        'cart_details' => $purchase_data['cart_details'],
        'gateway'      => 'algovoi',
        'status'       => 'pending',
    ];
    $payment_id = edd_insert_payment($payment_data);
    if (!$payment_id) {
        edd_set_error('algovoi_no_payment', __('Could not create EDD payment record.', 'algovoi-edd'));
        edd_send_back_to_checkout(['payment-mode' => 'algovoi']);
        return;
    }

    // EDD sends the customer back to the purchase-confirmation page when
    // they return from the hosted checkout. We append the payment ID so
    // the return handler can verify the right record.
    $return_url = add_query_arg('algovoi_payment_id', $payment_id, edd_get_success_page_uri());

    $resp = wp_remote_post(
        $api_base . '/v1/payment-links',
        [
            'timeout'   => 30,
            'sslverify' => true,
            'headers'   => [
                'Content-Type'  => 'application/json',
                'Authorization' => 'Bearer ' . $api_key,
                'X-Tenant-Id'   => $tenant,
            ],
            'body' => wp_json_encode([
                'amount'             => round($amount, 2),
                'currency'           => strtoupper(edd_get_currency()),
                'label'              => 'EDD #' . $payment_id,
                'preferred_network'  => $network,
                'redirect_url'       => $return_url,
                'expires_in_seconds' => 3600,
            ]),
        ]
    );

    if (is_wp_error($resp) || wp_remote_retrieve_response_code($resp) !== 201) {
        error_log('[algovoi-edd] create link failed: ' . (is_wp_error($resp) ? $resp->get_error_message() : wp_remote_retrieve_body($resp)));
        edd_update_payment_status($payment_id, 'failed');
        edd_set_error('algovoi_link_failed', __('Could not initiate payment. Please try again.', 'algovoi-edd'));
        edd_send_back_to_checkout(['payment-mode' => 'algovoi']);
        return;
    }

    $data = json_decode(wp_remote_retrieve_body($resp), true);
    if (!is_array($data) || empty($data['checkout_url'])) {
        edd_update_payment_status($payment_id, 'failed');
        edd_set_error('algovoi_bad_response', __('Gateway returned unexpected data.', 'algovoi-edd'));
        edd_send_back_to_checkout(['payment-mode' => 'algovoi']);
        return;
    }

    $token = '';
    if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $data['checkout_url'], $m)) {
        $token = $m[1];
    }

    edd_insert_payment_note($payment_id, 'AlgoVoi checkout created — network: ' . $network . ', token: ' . $token);
    edd_update_payment_meta($payment_id, '_algovoi_token',    $token);
    edd_update_payment_meta($payment_id, '_algovoi_api_base', $api_base);
    edd_update_payment_meta($payment_id, '_algovoi_network',  $network);

    wp_redirect($data['checkout_url']);
    exit;
});

/* ──────────────────────────────────────────────────────────────────────────
 * Return-from-checkout handler — cancel-bypass guard
 * ──────────────────────────────────────────────────────────────────────── */

add_action('template_redirect', function () {
    if (empty($_GET['algovoi_payment_id'])) {
        return;
    }
    $payment_id = (int) $_GET['algovoi_payment_id'];
    $payment    = edd_get_payment($payment_id);
    if (!$payment || $payment->gateway !== 'algovoi') {
        return;
    }
    if ($payment->status === 'publish' || $payment->status === 'complete') {
        return; // already paid, nothing to do
    }

    $token    = (string) edd_get_payment_meta($payment_id, '_algovoi_token');
    $api_base = (string) edd_get_payment_meta($payment_id, '_algovoi_api_base');

    if (algovoi_edd_verify_paid($api_base, $token)) {
        edd_update_payment_status($payment_id, 'publish');
        edd_insert_payment_note($payment_id, 'AlgoVoi payment verified on return (token ' . $token . ').');
    } else {
        edd_insert_payment_note($payment_id, 'AlgoVoi return hit but status not paid — order stays pending.');
    }
});

/* ──────────────────────────────────────────────────────────────────────────
 * Webhook — HMAC-verified inbound notifications
 * ──────────────────────────────────────────────────────────────────────── */

add_action('rest_api_init', function () {
    register_rest_route('algovoi-edd/v1', '/webhook', [
        'methods'             => 'POST',
        'callback'            => 'algovoi_edd_webhook',
        'permission_callback' => '__return_true',
    ]);
});

function algovoi_edd_webhook(WP_REST_Request $request) {
    $secret = (string) edd_get_option('algovoi_webhook_secret', '');
    if ($secret === '') {
        return new WP_Error('algovoi_no_secret', 'webhook secret not configured', ['status' => 500]);
    }

    $raw       = $request->get_body();
    $signature = (string) $request->get_header('x-algovoi-signature');

    // Type + length guards BEFORE HMAC compute — mirrors the AI adapters.
    if (!is_string($raw) || $raw === '' || strlen($raw) > 65536) {
        return new WP_Error('algovoi_bad_body', 'empty or oversized body', ['status' => 400]);
    }
    if ($signature === '') {
        return new WP_Error('algovoi_no_sig', 'missing signature', ['status' => 401]);
    }

    $expected = base64_encode(hash_hmac('sha256', $raw, $secret, true));
    if (!hash_equals($expected, $signature)) {
        return new WP_Error('algovoi_bad_sig', 'invalid signature', ['status' => 401]);
    }

    $payload = json_decode($raw, true);
    if (!is_array($payload)) {
        return new WP_Error('algovoi_bad_json', 'malformed payload', ['status' => 400]);
    }

    $order_ref = $payload['order_id'] ?? $payload['reference'] ?? null;
    $tx_id     = $payload['tx_id']    ?? $payload['transaction_id'] ?? null;
    if (!$order_ref || !$tx_id || strlen((string) $tx_id) > 200) {
        return new WP_Error('algovoi_bad_fields', 'missing order_id or tx_id', ['status' => 400]);
    }

    $payment_id = (int) $order_ref;
    $payment    = edd_get_payment($payment_id);
    if (!$payment || $payment->gateway !== 'algovoi') {
        return new WP_Error('algovoi_no_order', 'order not found', ['status' => 404]);
    }

    // Cross-check with the gateway — spoofed-but-HMAC-valid webhooks
    // (e.g. if secret ever leaks) can't mark paid without a real
    // gateway-verified payment.
    $token    = (string) edd_get_payment_meta($payment_id, '_algovoi_token');
    $api_base = (string) edd_get_payment_meta($payment_id, '_algovoi_api_base');
    if (!algovoi_edd_verify_paid($api_base, $token)) {
        return new WP_Error('algovoi_not_paid', 'payment not confirmed by gateway', ['status' => 402]);
    }

    // Idempotent — only transition once.
    if ($payment->status !== 'publish' && $payment->status !== 'complete') {
        edd_update_payment_status($payment_id, 'publish');
        edd_set_payment_transaction_id($payment_id, sanitize_text_field($tx_id));
        edd_insert_payment_note($payment_id, 'AlgoVoi webhook verified. TX: ' . esc_html($tx_id));
    }

    return ['ok' => true, 'payment_id' => $payment_id];
}

/* ──────────────────────────────────────────────────────────────────────────
 * Helpers
 * ──────────────────────────────────────────────────────────────────────── */

function algovoi_edd_is_https(string $url): bool {
    return str_starts_with($url, 'https://');
}

function algovoi_edd_verify_paid(string $api_base, string $token): bool {
    if ($token === '' || strlen($token) > 200) return false;
    if (!algovoi_edd_is_https($api_base))        return false;

    $r = wp_remote_get(
        rtrim($api_base, '/') . '/checkout/' . rawurlencode($token),
        ['timeout' => 15, 'sslverify' => true]
    );
    if (is_wp_error($r) || wp_remote_retrieve_response_code($r) !== 200) {
        return false;
    }
    $data = json_decode(wp_remote_retrieve_body($r), true);
    $status = is_array($data) ? ($data['status'] ?? '') : '';
    return in_array($status, ['paid', 'completed', 'confirmed'], true);
}
