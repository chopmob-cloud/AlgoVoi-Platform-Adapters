<?php
/**
 * Plugin Name:     AlgoVoi for GiveWP
 * Plugin URI:      https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Description:     Accept crypto donation payments (USDC on Algorand, VOI, Hedera & Stellar) via GiveWP.
 * Version:         1.0.0
 * Author:          AlgoVoi
 * Author URI:      https://algovoi.co.uk
 * License:         MIT
 * Text Domain:     algovoi-givewp
 * Requires PHP:    7.4
 * Requires at least: 5.8
 */

defined( 'ABSPATH' ) || exit;

define( 'ALGOVOI_GIVEWP_VERSION', '1.0.0' );
define( 'ALGOVOI_GIVEWP_FILE',    __FILE__ );
define( 'ALGOVOI_GIVEWP_DIR',     plugin_dir_path( __FILE__ ) );

add_action( 'plugins_loaded', function () {
    if ( ! class_exists( 'Give' ) ) {
        return;
    }
    require_once ALGOVOI_GIVEWP_DIR . 'src/AlgoVoiGateway.php';
    require_once ALGOVOI_GIVEWP_DIR . 'src/AlgoVoiSettings.php';

    // Register gateway
    add_filter( 'give_payment_gateways', function ( $gateways ) {
        $gateways['algovoi'] = [
            'admin_label'    => 'AlgoVoi — Crypto Donations',
            'checkout_label' => apply_filters( 'algovoi_givewp_checkout_label', 'Donate with Crypto (AlgoVoi)' ),
        ];
        return $gateways;
    } );

    // Settings
    add_filter( 'give_get_settings_gateways', [ 'AlgoVoi_GiveWP_Settings', 'add_settings' ] );

    // Offsite redirect
    add_action( 'give_gateway_algovoi', [ 'AlgoVoi_GiveWP_Gateway', 'process_payment' ] );

    // Return callback
    add_action( 'init', [ 'AlgoVoi_GiveWP_Gateway', 'handle_return' ] );

    // Webhook endpoint
    add_action( 'init', function () {
        if ( ! empty( $_GET['algovoi_givewp_webhook'] ) ) {
            AlgoVoi_GiveWP_Gateway::handle_webhook();
        }
    } );
}, 20 );
