<?php
defined( 'ABSPATH' ) || exit;

class AlgoVoi_GiveWP_Gateway {

    // ── Process donation — redirect to AlgoVoi checkout ────────────────────────

    public static function process_payment( $payment_data ) {
        $settings  = self::get_settings();
        $api_key   = sanitize_text_field( $settings['api_key'] ?? '' );
        $tenant_id = sanitize_text_field( $settings['tenant_id'] ?? '' );
        $api_base  = esc_url_raw( rtrim( $settings['api_base'] ?? 'https://api1.ilovechicken.co.uk', '/' ) );
        $network   = sanitize_text_field( $settings['network'] ?? 'algorand_mainnet' );

        // Validate API base is HTTPS
        if ( strpos( $api_base, 'https://' ) !== 0 ) {
            give_set_error( 'algovoi_error', __( 'AlgoVoi configuration error. Please contact the site admin.', 'algovoi-givewp' ) );
            give_send_back_to_checkout( '?payment-mode=algovoi' );
            return;
        }

        $amount = floatval( $payment_data['price'] );

        // Sanity: amount must be positive and sensible
        if ( $amount <= 0 || $amount > 1000000 ) {
            give_set_error( 'algovoi_amount', __( 'Invalid donation amount.', 'algovoi-givewp' ) );
            give_send_back_to_checkout( '?payment-mode=algovoi' );
            return;
        }

        // Create pending payment record
        $payment_id = give_insert_payment( $payment_data );
        if ( ! $payment_id ) {
            give_set_error( 'algovoi_payment', __( 'Could not create payment record. Please try again.', 'algovoi-givewp' ) );
            give_send_back_to_checkout( '?payment-mode=algovoi' );
            return;
        }

        $form_title = get_the_title( $payment_data['post_data']['give-form-id'] ?? 0 );
        $label      = $form_title ? $form_title . ' — Donation' : 'Donation';

        $return_url = add_query_arg(
            [ 'algovoi_givewp_return' => '1', 'payment_id' => $payment_id ],
            get_permalink( $payment_data['post_data']['give-form-id'] ?? 0 ) ?: site_url( '/' )
        );

        $payload = wp_json_encode( [
            'amount'            => $amount,
            'currency'          => give_get_currency(),
            'label'             => mb_substr( $label, 0, 200 ),
            'preferred_network' => $network,
            'redirect_url'      => $return_url,
        ] );

        $response = wp_remote_post(
            $api_base . '/v1/payment-links',
            [
                'headers'   => [
                    'Authorization' => 'Bearer ' . $api_key,
                    'X-Tenant-Id'   => $tenant_id,
                    'Content-Type'  => 'application/json',
                ],
                'body'      => $payload,
                'timeout'   => 15,
                'sslverify' => true,
            ]
        );

        if ( is_wp_error( $response ) ) {
            give_update_payment_status( $payment_id, 'failed' );
            give_set_error( 'algovoi_api', __( 'Could not connect to AlgoVoi. Please try again.', 'algovoi-givewp' ) );
            give_send_back_to_checkout( '?payment-mode=algovoi' );
            return;
        }

        $code = wp_remote_retrieve_response_code( $response );
        $body = json_decode( wp_remote_retrieve_body( $response ), true );

        if ( $code !== 200 || empty( $body['checkout_url'] ) ) {
            give_update_payment_status( $payment_id, 'failed' );
            give_set_error( 'algovoi_api', __( 'AlgoVoi returned an error. Please try again.', 'algovoi-givewp' ) );
            give_send_back_to_checkout( '?payment-mode=algovoi' );
            return;
        }

        $checkout_url = esc_url_raw( $body['checkout_url'] );

        // Prevent open redirect — must be HTTPS
        if ( strpos( $checkout_url, 'https://' ) !== 0 ) {
            give_update_payment_status( $payment_id, 'failed' );
            give_set_error( 'algovoi_api', __( 'AlgoVoi returned an invalid redirect URL.', 'algovoi-givewp' ) );
            give_send_back_to_checkout( '?payment-mode=algovoi' );
            return;
        }

        // Stash token for verification on return
        give_update_meta( $payment_id, '_algovoi_token', sanitize_text_field( $body['token'] ?? '' ) );
        give_update_payment_status( $payment_id, 'pending' );

        wp_safe_redirect( $checkout_url );
        exit;
    }

    // ── Return handler — verify payment on return ──────────────────────────────

    public static function handle_return() {
        // phpcs:ignore WordPress.Security.NonceVerification.Recommended -- return handler uses token-based verification, not nonce.
        if ( empty( $_GET['algovoi_givewp_return'] ) || empty( $_GET['payment_id'] ) ) {
            return;
        }

        // phpcs:ignore WordPress.Security.NonceVerification.Recommended
        $payment_id = absint( $_GET['payment_id'] );
        $token      = sanitize_text_field( give_get_meta( $payment_id, '_algovoi_token', true ) );
        $settings   = self::get_settings();
        $api_base   = esc_url_raw( rtrim( $settings['api_base'] ?? 'https://api1.ilovechicken.co.uk', '/' ) );

        if ( empty( $token ) || strpos( $api_base, 'https://' ) !== 0 ) {
            return;
        }

        $response = wp_remote_get(
            $api_base . '/checkout/' . rawurlencode( $token ) . '/status',
            [ 'timeout' => 15, 'sslverify' => true ]
        );

        if ( is_wp_error( $response ) ) {
            return;
        }

        $body   = json_decode( wp_remote_retrieve_body( $response ), true );
        $status = sanitize_text_field( $body['status'] ?? '' );

        if ( in_array( $status, [ 'paid', 'completed', 'confirmed' ], true ) ) {
            give_update_payment_status( $payment_id, 'publish' );
            give_set_payment_transaction_id( $payment_id, sanitize_text_field( $body['tx_id'] ?? $token ) );
            give_send_to_success_page();
        }
    }

    // ── Webhook handler ────────────────────────────────────────────────────────

    public static function handle_webhook() {
        $settings = self::get_settings();
        $secret   = $settings['webhook_secret'] ?? '';

        $raw_body = file_get_contents( 'php://input' );

        // Cap body size
        if ( strlen( $raw_body ) > 65536 ) {
            status_header( 400 );
            exit;
        }

        // Verify HMAC signature if secret is configured
        if ( ! empty( $secret ) ) {
            $signature = sanitize_text_field( wp_unslash( $_SERVER['HTTP_X_ALGOVOI_SIGNATURE'] ?? '' ) );
            $expected  = hash_hmac( 'sha256', $raw_body, $secret );
            if ( ! hash_equals( $expected, $signature ) ) {
                status_header( 401 );
                exit;
            }
        }

        $payload = json_decode( $raw_body, true );
        if ( ! is_array( $payload ) || ( $payload['event_type'] ?? '' ) !== 'payment.confirmed' ) {
            status_header( 200 );
            exit;
        }

        $token = sanitize_text_field( $payload['token'] ?? '' );
        if ( empty( $token ) ) {
            status_header( 200 );
            exit;
        }

        // Find the payment by token
        // phpcs:disable WordPress.DB.SlowDBQuery.slow_db_query_meta_key, WordPress.DB.SlowDBQuery.slow_db_query_meta_value -- one-shot webhook lookup on indexed meta.
        $payments = give_get_payments( [
            'meta_key'   => '_algovoi_token',
            'meta_value' => $token,
            'number'     => 1,
        ] );
        // phpcs:enable WordPress.DB.SlowDBQuery.slow_db_query_meta_key, WordPress.DB.SlowDBQuery.slow_db_query_meta_value

        if ( ! empty( $payments ) ) {
            $payment_id = $payments[0]->ID;
            give_update_payment_status( $payment_id, 'publish' );
            give_set_payment_transaction_id( $payment_id, sanitize_text_field( $payload['tx_id'] ?? $token ) );
        }

        status_header( 200 );
        exit;
    }

    // ── Helpers ────────────────────────────────────────────────────────────────

    private static function get_settings(): array {
        return [
            'api_key'        => give_get_option( 'algovoi_api_key', '' ),
            'tenant_id'      => give_get_option( 'algovoi_tenant_id', '' ),
            'api_base'       => give_get_option( 'algovoi_api_base', 'https://api1.ilovechicken.co.uk' ),
            'network'        => give_get_option( 'algovoi_network', 'algorand_mainnet' ),
            'webhook_secret' => give_get_option( 'algovoi_webhook_secret', '' ),
        ];
    }
}
