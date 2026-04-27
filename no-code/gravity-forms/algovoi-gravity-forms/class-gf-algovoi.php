<?php
defined( 'ABSPATH' ) || exit;

/**
 * AlgoVoi Gravity Forms payment add-on.
 *
 * Extends GFPaymentAddOn so Gravity Forms handles all the order/entry management;
 * we only need to implement the redirect-to-checkout and post-payment flows.
 */
// phpcs:ignore WordPress.NamingConventions.PrefixAllGlobals.NonPrefixedClassFound -- extends GFPaymentAddOn, name must follow GF convention.
class GF_AlgoVoi extends GFPaymentAddOn {

    protected $_version     = ALGOVOI_GF_VERSION;
    protected $_slug        = 'algovoi-gravity-forms';
    protected $_path        = 'algovoi-gravity-forms/algovoi-gravity-forms.php';
    protected $_full_path   = __FILE__;
    protected $_title       = 'AlgoVoi Crypto Payments';
    protected $_short_title = 'AlgoVoi';

    // Hosted / redirect payment model
    protected $_supports_callbacks = true;

    private static $_instance = null;

    public static function get_instance() {
        if ( null === self::$_instance ) {
            self::$_instance = new self();
        }
        return self::$_instance;
    }

    // ── Plugin settings ────────────────────────────────────────────────────────

    public function plugin_settings_fields() {
        return [
            [
                'title'  => 'AlgoVoi Credentials',
                'fields' => [
                    [
                        'name'              => 'api_key',
                        'label'             => 'API Key',
                        'type'              => 'text',
                        'class'             => 'medium',
                        'feedback_callback' => [ $this, 'is_valid_api_key' ],
                        'tooltip'           => 'Your AlgoVoi API key (starts with algv_). Get it from dash.algovoi.co.uk → Settings.',
                    ],
                    [
                        'name'    => 'tenant_id',
                        'label'   => 'Tenant ID',
                        'type'    => 'text',
                        'class'   => 'medium',
                        'tooltip' => 'Your AlgoVoi tenant UUID. Found in dash.algovoi.co.uk → Settings.',
                    ],
                    [
                        'name'    => 'api_base',
                        'label'   => 'API Base URL',
                        'type'    => 'text',
                        'class'   => 'medium',
                        'default' => 'https://api1.ilovechicken.co.uk',
                        'tooltip' => 'Leave as default unless using AlgoVoi Cloud.',
                    ],
                    [
                        'name'  => 'payout_algorand',
                        'label' => 'Payout Address — Algorand',
                        'type'  => 'text',
                        'class' => 'medium',
                    ],
                    [
                        'name'  => 'payout_voi',
                        'label' => 'Payout Address — VOI',
                        'type'  => 'text',
                        'class' => 'medium',
                    ],
                    [
                        'name'  => 'payout_hedera',
                        'label' => 'Payout Address — Hedera',
                        'type'  => 'text',
                        'class' => 'medium',
                    ],
                    [
                        'name'  => 'payout_stellar',
                        'label' => 'Payout Address — Stellar',
                        'type'  => 'text',
                        'class' => 'medium',
                    ],
                    [
                        'name'    => 'webhook_secret',
                        'label'   => 'Webhook Secret',
                        'type'    => 'text',
                        'class'   => 'medium',
                        'tooltip' => 'AlgoVoi webhook signing secret for HMAC-SHA256 verification.',
                    ],
                ],
            ],
        ];
    }

    public function is_valid_api_key( $value ) {
        return ( strpos( $value, 'algv_' ) === 0 );
    }

    // ── Feed settings ──────────────────────────────────────────────────────────

    public function feed_settings_fields() {
        return [
            [
                'title'  => 'AlgoVoi Feed Settings',
                'fields' => [
                    [
                        'name'     => 'feedName',
                        'label'    => 'Feed Name',
                        'type'     => 'text',
                        'required' => true,
                        'class'    => 'medium',
                        'default'  => 'AlgoVoi Payment',
                    ],
                    [
                        'name'          => 'paymentAmount',
                        'label'         => 'Payment Amount',
                        'type'          => 'select',
                        'required'      => true,
                        'choices'       => $this->product_amount_choices(),
                        'default_value' => 'form_total',
                    ],
                    [
                        'name'    => 'network',
                        'label'   => 'Network',
                        'type'    => 'select',
                        'choices' => [
                            [ 'label' => 'Algorand — USDC',          'value' => 'algorand_mainnet' ],
                            [ 'label' => 'VOI — aUSDC',              'value' => 'voi_mainnet' ],
                            [ 'label' => 'Hedera — USDC',            'value' => 'hedera_mainnet' ],
                            [ 'label' => 'Stellar — USDC',           'value' => 'stellar_mainnet' ],
                            [ 'label' => 'Base — USDC',              'value' => 'base_mainnet' ],
                            [ 'label' => 'Solana — USDC',            'value' => 'solana_mainnet' ],
                            [ 'label' => 'Tempo — USDC',             'value' => 'tempo_mainnet' ],
                            [ 'label' => 'Algorand — ALGO (native)', 'value' => 'algorand_mainnet_algo' ],
                            [ 'label' => 'VOI — VOI (native)',       'value' => 'voi_mainnet_voi' ],
                            [ 'label' => 'Hedera — HBAR (native)',   'value' => 'hedera_mainnet_hbar' ],
                            [ 'label' => 'Stellar — XLM (native)',   'value' => 'stellar_mainnet_xlm' ],
                        ],
                        'default' => 'algorand_mainnet',
                    ],
                    [
                        'name'  => 'customLabel',
                        'label' => 'Payment Label',
                        'type'  => 'text',
                        'class' => 'medium',
                        'tooltip' => 'Label shown on the AlgoVoi checkout page. Defaults to the form name.',
                    ],
                ],
            ],
        ];
    }

    // ── Redirect to AlgoVoi checkout ───────────────────────────────────────────

    public function redirect_url( $feed, $submission_data, $form, $entry ) {
        $settings   = $this->get_plugin_settings();
        $api_key    = sanitize_text_field( $settings['api_key'] ?? '' );
        $tenant_id  = sanitize_text_field( $settings['tenant_id'] ?? '' );
        $api_base   = esc_url_raw( rtrim( $settings['api_base'] ?? 'https://api1.ilovechicken.co.uk', '/' ) );

        // Validate API base is HTTPS
        if ( strpos( $api_base, 'https://' ) !== 0 ) {
            $this->log_error( 'AlgoVoi: api_base must use HTTPS.' );
            return '';
        }

        $amount   = floatval( $submission_data['payment_amount'] ?? 0 );
        $network  = sanitize_text_field( $feed['meta']['network'] ?? 'algorand_mainnet' );
        $label    = sanitize_text_field(
            $feed['meta']['customLabel'] ?: ( $form['title'] ?? 'Gravity Forms Payment' )
        );

        // Sanity: amount must be positive and sensible
        if ( $amount <= 0 || $amount > 1000000 ) {
            $this->log_error( 'AlgoVoi: invalid payment amount: ' . $amount );
            return '';
        }

        $return_url = add_query_arg(
            [ 'algovoi_callback' => '1', 'entry_id' => $entry['id'] ],
            site_url( '/' )
        );

        $payload = wp_json_encode( [
            'amount'            => $amount,
            'currency'          => 'USD',
            'label'             => mb_substr( $label, 0, 200 ),
            'preferred_network' => $network,
            'redirect_url'      => $return_url,
        ] );

        $response = wp_remote_post(
            $api_base . '/v1/payment-links',
            [
                'headers' => [
                    'Authorization' => 'Bearer ' . $api_key,
                    'X-Tenant-Id'   => $tenant_id,
                    'Content-Type'  => 'application/json',
                ],
                'body'    => $payload,
                'timeout' => 15,
                'sslverify' => true,
            ]
        );

        if ( is_wp_error( $response ) ) {
            $this->log_error( 'AlgoVoi: HTTP error: ' . $response->get_error_message() );
            return '';
        }

        $code = wp_remote_retrieve_response_code( $response );
        $body = json_decode( wp_remote_retrieve_body( $response ), true );

        if ( $code !== 200 || empty( $body['checkout_url'] ) ) {
            $this->log_error( 'AlgoVoi: unexpected response: ' . $code );
            return '';
        }

        $checkout_url = esc_url_raw( $body['checkout_url'] );

        // Must be an HTTPS URL to prevent open redirect
        if ( strpos( $checkout_url, 'https://' ) !== 0 ) {
            $this->log_error( 'AlgoVoi: checkout_url is not HTTPS.' );
            return '';
        }

        // Stash the token so the callback can verify it
        gform_update_meta( $entry['id'], 'algovoi_token', sanitize_text_field( $body['token'] ?? '' ) );
        GFAPI::update_entry_property( $entry['id'], 'payment_status', 'Processing' );

        return $checkout_url;
    }

    // ── Webhook callback ───────────────────────────────────────────────────────

    public function callback() {
        // AlgoVoi posts to our return URL with ?algovoi_callback=1&entry_id=X
        // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- GF callback uses HMAC signature verification, not nonce.
        if ( empty( $_GET['algovoi_callback'] ) || empty( $_GET['entry_id'] ) ) {
            return false;
        }

        // phpcs:ignore WordPress.Security.NonceVerification.Recommended
        $entry_id = absint( $_GET['entry_id'] );
        $entry    = GFAPI::get_entry( $entry_id );

        if ( is_wp_error( $entry ) ) {
            return false;
        }

        // Read the stored token and verify on-chain
        $token    = sanitize_text_field( gform_get_meta( $entry_id, 'algovoi_token' ) );
        $settings = $this->get_plugin_settings();
        $api_key  = sanitize_text_field( $settings['api_key'] ?? '' );
        $api_base = esc_url_raw( rtrim( $settings['api_base'] ?? 'https://api1.ilovechicken.co.uk', '/' ) );

        if ( empty( $token ) || strpos( $api_base, 'https://' ) !== 0 ) {
            return false;
        }

        $response = wp_remote_get(
            $api_base . '/checkout/' . rawurlencode( $token ) . '/status',
            [ 'timeout' => 15, 'sslverify' => true ]
        );

        if ( is_wp_error( $response ) ) {
            return false;
        }

        $body   = json_decode( wp_remote_retrieve_body( $response ), true );
        $status = sanitize_text_field( $body['status'] ?? '' );

        if ( in_array( $status, [ 'paid', 'completed', 'confirmed' ], true ) ) {
            $action = [
                'type'             => 'complete_payment',
                'payment_status'   => 'Paid',
                'payment_date'     => gmdate( 'Y-m-d H:i:s' ),
                'payment_amount'   => $entry['payment_amount'],
                'transaction_id'   => sanitize_text_field( $body['tx_id'] ?? $token ),
                'transaction_type' => 1,
                'entry_id'         => $entry_id,
            ];
            $this->fulfill_order( $entry, 'complete_payment', $action );
            GFAPI::update_entry_property( $entry_id, 'payment_status', 'Paid' );
        }

        return true;
    }

    // ── Webhook signature verification ─────────────────────────────────────────

    public function verify_payment_webhook() {
        $settings = $this->get_plugin_settings();
        $secret   = $settings['webhook_secret'] ?? '';

        if ( empty( $secret ) ) {
            return false;
        }

        $raw_body  = file_get_contents( 'php://input' );
        $signature = sanitize_text_field( wp_unslash( $_SERVER['HTTP_X_ALGOVOI_SIGNATURE'] ?? '' ) );

        if ( strlen( $raw_body ) > 65536 ) {
            return false;
        }

        $expected = hash_hmac( 'sha256', $raw_body, $secret );

        if ( ! hash_equals( $expected, $signature ) ) {
            return false;
        }

        $payload = json_decode( $raw_body, true );
        if ( ! is_array( $payload ) ) {
            return false;
        }

        return $payload;
    }
}
