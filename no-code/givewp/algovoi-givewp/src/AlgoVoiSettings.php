<?php
defined( 'ABSPATH' ) || exit;

class AlgoVoi_GiveWP_Settings {

    public static function add_settings( $settings ) {
        $algovoi_settings = [
            [
                'id'   => 'algovoi_settings_title',
                'type' => 'title',
                'name' => __( 'AlgoVoi Crypto Payments', 'algovoi-givewp' ),
            ],
            [
                'id'      => 'algovoi_api_key',
                'name'    => __( 'API Key', 'algovoi-givewp' ),
                'desc'    => __( 'Your AlgoVoi API key (starts with algv_). Get it from dash.algovoi.co.uk → Settings.', 'algovoi-givewp' ),
                'type'    => 'text',
                'default' => '',
            ],
            [
                'id'      => 'algovoi_tenant_id',
                'name'    => __( 'Tenant ID', 'algovoi-givewp' ),
                'desc'    => __( 'Your AlgoVoi tenant UUID. Found in dash.algovoi.co.uk → Settings.', 'algovoi-givewp' ),
                'type'    => 'text',
                'default' => '',
            ],
            [
                'id'      => 'algovoi_api_base',
                'name'    => __( 'API Base URL', 'algovoi-givewp' ),
                'desc'    => __( 'Leave as default unless using AlgoVoi Cloud (https://cloud.algovoi.co.uk).', 'algovoi-givewp' ),
                'type'    => 'text',
                'default' => 'https://api1.ilovechicken.co.uk',
            ],
            [
                'id'      => 'algovoi_network',
                'name'    => __( 'Default Network', 'algovoi-givewp' ),
                'desc'    => __( 'Blockchain / asset donors should pay on.', 'algovoi-givewp' ),
                'type'    => 'select',
                'default' => 'algorand_mainnet',
                'options' => [
                    'algorand_mainnet'      => 'Algorand — USDC',
                    'voi_mainnet'           => 'VOI — aUSDC',
                    'hedera_mainnet'        => 'Hedera — USDC',
                    'stellar_mainnet'       => 'Stellar — USDC',
                    'algorand_mainnet_algo' => 'Algorand — ALGO (native)',
                    'voi_mainnet_voi'       => 'VOI — VOI (native)',
                    'hedera_mainnet_hbar'   => 'Hedera — HBAR (native)',
                    'stellar_mainnet_xlm'   => 'Stellar — XLM (native)',
                ],
            ],
            [
                'id'      => 'algovoi_payout_algorand',
                'name'    => __( 'Payout Address — Algorand', 'algovoi-givewp' ),
                'type'    => 'text',
                'default' => '',
            ],
            [
                'id'      => 'algovoi_payout_voi',
                'name'    => __( 'Payout Address — VOI', 'algovoi-givewp' ),
                'type'    => 'text',
                'default' => '',
            ],
            [
                'id'      => 'algovoi_payout_hedera',
                'name'    => __( 'Payout Address — Hedera', 'algovoi-givewp' ),
                'desc'    => __( 'e.g. 0.0.123456', 'algovoi-givewp' ),
                'type'    => 'text',
                'default' => '',
            ],
            [
                'id'      => 'algovoi_payout_stellar',
                'name'    => __( 'Payout Address — Stellar', 'algovoi-givewp' ),
                'desc'    => __( 'Starts with G.', 'algovoi-givewp' ),
                'type'    => 'text',
                'default' => '',
            ],
            [
                'id'      => 'algovoi_webhook_secret',
                'name'    => __( 'Webhook Secret', 'algovoi-givewp' ),
                'desc'    => __( 'AlgoVoi webhook signing secret. Found in Settings → Webhooks. Webhook URL: ' . add_query_arg( 'algovoi_givewp_webhook', '1', site_url( '/' ) ), 'algovoi-givewp' ),
                'type'    => 'text',
                'default' => '',
            ],
            [
                'id'   => 'algovoi_settings_end',
                'type' => 'sectionend',
            ],
        ];

        return array_merge( $settings, $algovoi_settings );
    }
}
