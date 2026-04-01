<?php
/**
 * Plugin Name: WooCommerce Basic Auth
 * Description: Enables HTTP Basic Authentication for the WooCommerce REST API.
 * Version: 1.2
 */
if ( ! defined( 'ABSPATH' ) ) exit;

add_filter( 'determine_current_user', function( $user_id ) {
    if ( $user_id || empty( $_SERVER['PHP_AUTH_USER'] ) ) {
        return $user_id;
    }

    global $wpdb;

    $consumer_key    = wc_clean( wp_unslash( $_SERVER['PHP_AUTH_USER'] ) );
    $consumer_secret = wc_clean( wp_unslash( $_SERVER['PHP_AUTH_PW'] ?? '' ) );
    $key_hash        = wc_api_hash( $consumer_key );

    $row = $wpdb->get_row( $wpdb->prepare(
        "SELECT user_id, consumer_secret FROM {$wpdb->prefix}woocommerce_api_keys WHERE consumer_key = %s",
        $key_hash
    ) );

    if ( $row && hash_equals( $row->consumer_secret, $consumer_secret ) ) {
        return (int) $row->user_id;
    }

    return $user_id;
}, 20 );
