<?php
/**
 * Plugin Name:          AlgoVoi Payment Gateway
 * Plugin URI:           https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Description:          Accept USDC stablecoin payments on Algorand, VOI, Hedera, and Stellar via hosted checkout or browser extension. No crypto knowledge required — works alongside any existing payment method.
 * Version:              2.4.2
 * Requires at least:    6.4
 * Requires PHP:         8.0
 * Tested up to:         6.9.4
 * Requires Plugins:     woocommerce
 * WC requires at least: 7.0
 * WC tested up to:      10.6.2
 * Author:               AlgoVoi
 * Author URI:           https://api1.ilovechicken.co.uk
 * License:              BUSL-1.1
 * License URI:          https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters/blob/master/LICENSE
 * Text Domain:          algovoi

 * AlgoVoi docs: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 — see LICENSE for details.
 */
if (!defined('ABSPATH')) exit;

add_filter('woocommerce_payment_gateways', function ($gateways) {
    $gateways[] = 'WC_AlgoVoi_Gateway';
    $gateways[] = 'WC_AlgoVoi_Extension_Gateway';
    return $gateways;
});

// REST endpoint: proxy extension-payment verification to AlgoVoi
add_action('rest_api_init', function () {
    register_rest_route('algovoi/v1', '/orders/(?P<id>\d+)/verify', array(
        'methods'             => 'POST',
        'callback'            => 'algovoi_ext_verify_payment',
        'permission_callback' => '__return_true',
    ));
});

function algovoi_ext_verify_payment($request) {
    $order_id  = (int) $request->get_param('id');
    $body      = $request->get_json_params();
    $tx_id     = sanitize_text_field(isset($body['tx_id']) ? $body['tx_id'] : '');
    $order_key = sanitize_text_field(isset($body['order_key']) ? $body['order_key'] : '');
    if (!$tx_id || strlen($tx_id) > 200)
        return new WP_Error('missing_tx', 'tx_id required', array('status' => 400));
    $order = wc_get_order($order_id);
    if (!$order || !hash_equals($order->get_order_key(), $order_key))
        return new WP_Error('not_found', 'Order not found', array('status' => 404));
    if ($order->is_paid())
        return new WP_REST_Response(array('success' => true, 'already_paid' => true), 200);
    $token = $order->get_meta('_algovoi_token');
    if (!$token) return new WP_Error('no_token', 'No AlgoVoi token', array('status' => 400));
    $vurl = rtrim($order->get_meta('_algovoi_api_base'), '/') . '/checkout/' . rawurlencode($token) . '/verify';
    $resp = wp_remote_post($vurl, array('timeout' => 30, 'sslverify' => true,
        'headers' => array('Content-Type' => 'application/json'),
        'body'    => wp_json_encode(array('tx_id' => $tx_id))));
    if (is_wp_error($resp)) return new WP_Error('upstream', $resp->get_error_message(), array('status' => 502));
    $code = wp_remote_retrieve_response_code($resp);
    $data = json_decode(wp_remote_retrieve_body($resp), true);
    if ($code === 200) {
        $order->payment_complete($tx_id);
        $order->add_order_note('AlgoVoi extension payment verified. TX: ' . esc_html($tx_id));
        return new WP_REST_Response(array('success' => true, 'tx_id' => $tx_id), 200);
    }
    return new WP_REST_Response(
        array('detail' => isset($data['detail']) ? $data['detail'] : 'Verification failed'),
        $code >= 400 ? $code : 422);
}

/* ─── Shared helpers ─────────────────────────────────────────────────────── */

/**
 * Create a payment link via POST /v1/payment-links.
 * Returns the full decoded response array on success, null on failure.
 */
function algovoi_create_link($api_base, $api_key, $tenant_id, $amount, $currency, $label, $network, $redirect_url = null) {
    $payload = array(
        'amount'             => (float) $amount,
        'currency'           => strtoupper($currency),
        'label'              => $label,
        'preferred_network'  => $network,
    );
    if ($redirect_url) $payload['redirect_url'] = $redirect_url;

    $resp = wp_remote_post(
        rtrim($api_base, '/') . '/v1/payment-links',
        array(
            'timeout'   => 30,
            'sslverify' => true,
            'headers'   => array(
                'Content-Type'  => 'application/json',
                'Authorization' => 'Bearer ' . $api_key,
                'X-Tenant-Id'   => $tenant_id,
            ),
            'body' => wp_json_encode($payload),
        )
    );
    if (is_wp_error($resp)) {
        wc_get_logger()->error('AlgoVoi create_link: ' . $resp->get_error_message(), array('source' => 'algovoi'));
        return null;
    }
    $code = wp_remote_retrieve_response_code($resp);
    $data = json_decode(wp_remote_retrieve_body($resp), true);
    if ($code !== 201 || empty($data['checkout_url'])) {
        wc_get_logger()->error('AlgoVoi create_link HTTP ' . $code . ': ' . wp_remote_retrieve_body($resp), array('source' => 'algovoi'));
        return null;
    }
    return $data;
}

/**
 * Fetch the checkout page and extract receiver address and memo only.
 */
function algovoi_parse_checkout($url, $api_base = '') {
    // SSRF guard: checkout URL must share the same host as the configured API base
    if ($api_base) {
        $expected_host = wp_parse_url(rtrim($api_base, '/'), PHP_URL_HOST);
        $url_host      = wp_parse_url($url, PHP_URL_HOST);
        if (!$expected_host || $url_host !== $expected_host) {
            wc_get_logger()->error('AlgoVoi: checkout URL host mismatch — possible SSRF blocked', array('source' => 'algovoi'));
            return null;
        }
    }
    $r = wp_remote_get($url, array('timeout' => 15, 'sslverify' => true));
    if (is_wp_error($r) || wp_remote_retrieve_response_code($r) !== 200) return null;
    $html = wp_remote_retrieve_body($r);
    // Match: onclick="copyText('ADDR58CHARS', this)" — address is the first 58-char base32 value
    if (!preg_match('/onclick="copyText\(\'([A-Z2-7]{58})\'/', $html, $m)) return null;
    $receiver = $m[1];
    // Match: onclick="copyText('algovoi:TOKEN', this)"
    if (!preg_match('/onclick="copyText\(\'(algovoi:[A-Za-z0-9_-]+)\'/', $html, $m)) return null;
    $memo = $m[1];
    return array('receiver' => $receiver, 'memo' => $memo);
}

/**
 * Render the chain radio selector.
 * $chains: array of [network_value, label, ticker, colour, icon] rows.
 */
function algovoi_chain_selector_html($field_name, $chains = null) {
    if ($chains === null) {
        $chains = [
            ['algorand_mainnet', 'Algorand', 'USDC',  '#3b82f6', '&#9672;'],
            ['voi_mainnet',      'VOI',      'aUSDC', '#8b5cf6', '&#9670;'],
        ];
    }
    ?>
    <div class="av-chain-selector" style="margin-top:.75rem;">
        <p style="font-size:.78rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;
                  color:#6b7280;margin:0 0 .6rem;">Select network</p>
        <div style="display:flex;gap:.75rem;flex-wrap:wrap;">
            <?php foreach ($chains as [$val, $label, $ticker, $colour, $icon]) : ?>
            <label class="av-chain-opt" style="flex:1;min-width:130px;cursor:pointer;">
                <input type="radio" name="<?php echo esc_attr($field_name); ?>"
                       value="<?php echo esc_attr($val); ?>"
                       style="display:none;"
                       onchange="avChainSelect(this)">
                <div class="av-chain-card" data-colour="<?php echo esc_attr($colour); ?>"
                     style="padding:.85rem 1rem;background:#1e2130;border:2px solid #2a2d3a;
                            border-radius:10px;transition:border-color .15s,background .15s;text-align:center;">
                    <span style="font-size:1.1rem;color:<?php echo esc_attr($colour); ?>;"><?php echo $icon; ?></span>
                    <span style="font-weight:700;color:#f1f2f6;margin-left:.4rem;"><?php echo esc_html($label); ?></span>
                    <span style="display:block;font-size:.75rem;color:#6b7280;margin-top:.2rem;">
                        Pay with <?php echo esc_html($ticker); ?>
                    </span>
                </div>
            </label>
            <?php endforeach; ?>
        </div>
        <div class="av-chain-error" style="display:none;margin-top:.5rem;font-size:.8rem;color:#ef4444;">
            Please select a network to continue.
        </div>
    </div>
    <script>
    if (typeof avChainSelect === 'undefined') {
        function avChainSelect(radio) {
            radio.closest('.av-chain-selector').querySelectorAll('.av-chain-card').forEach(function(c) {
                c.style.borderColor = '#2a2d3a';
                c.style.background  = '#1e2130';
            });
            var card = radio.closest('.av-chain-opt').querySelector('.av-chain-card');
            card.style.borderColor = card.dataset.colour;
            card.style.background  = 'rgba(59,130,246,.08)';
            radio.closest('.av-chain-selector').querySelector('.av-chain-error').style.display = 'none';
        }
    }
    </script>
    <?php
}

/* ─── Asset map (asset_id → algod URL, ticker, decimals, chain label) ────── */
define('ALGOVOI_AM', array(
    '31566704' => array('ticker' => 'USDC',  'dec' => 6, 'algod' => 'https://mainnet-api.algonode.cloud', 'chain' => 'Algorand', 'colour' => '#3b82f6'),
    '302190'   => array('ticker' => 'aUSDC', 'dec' => 6, 'algod' => 'https://mainnet-api.voi.nodely.io',  'chain' => 'VOI',      'colour' => '#8b5cf6'),
));

add_action('plugins_loaded', function () {
    if (!class_exists('WC_Payment_Gateway')) return;

    /* ════════════════════════════════════════════════════════════════════════
     * Gateway 1: Hosted checkout redirect
     * ════════════════════════════════════════════════════════════════════════ */
    class WC_AlgoVoi_Gateway extends WC_Payment_Gateway {

        public function __construct() {
            $this->id = 'algovoi'; $this->has_fields = true;
            $this->method_title = 'AlgoVoi';
            $this->method_description = 'USDC (Algorand), aUSDC (VOI) or USDC (Hedera) via hosted checkout.';
            $this->init_form_fields(); $this->init_settings();
            $this->title       = $this->get_option('title', 'AlgoVoi - Pay with Crypto');
            $this->description = $this->get_option('description', 'Pay with USDC on Algorand or aUSDC on VOI.');
            add_action('woocommerce_update_options_payment_gateways_' . $this->id, array($this, 'process_admin_options'));
        }

        public function init_form_fields() {
            $this->form_fields = array(
                'enabled'     => array('title' => 'Enable/Disable', 'type' => 'checkbox', 'label' => 'Enable AlgoVoi', 'default' => 'yes'),
                'title'       => array('title' => 'Title',       'type' => 'text',     'default' => 'AlgoVoi - Pay with Crypto'),
                'description' => array('title' => 'Description', 'type' => 'textarea', 'default' => 'Pay with USDC on Algorand or Hedera, or aUSDC on VOI.'),
                'api_base'    => array('title' => 'API Base URL', 'type' => 'text',     'default' => 'https://api1.ilovechicken.co.uk'),
                'api_key'     => array('title' => 'API Key',     'type' => 'password', 'default' => ''),
                'tenant_id'   => array('title' => 'Tenant ID',   'type' => 'text',     'default' => ''),
            );
        }

        public function payment_fields() {
            if ($desc = $this->get_description())
                echo '<p style="margin:0 0 .5rem;color:#9ca3af;font-size:.9rem;">' . wp_kses_post($desc) . '</p>';
            algovoi_chain_selector_html('algovoi_network', [
                ['algorand_mainnet', 'Algorand', 'USDC',  '#3b82f6', '&#9672;'],
                ['voi_mainnet',      'VOI',      'aUSDC', '#8b5cf6', '&#9670;'],
                ['hedera_mainnet',   'Hedera',   'USDC',  '#00a9a5', '&#9711;'],
                ['stellar_mainnet',  'Stellar',  'USDC',  '#7C63D0', '&#9733;'],
            ]);
        }

        public function validate_fields() {
            $net = isset($_POST['algovoi_network']) ? sanitize_text_field($_POST['algovoi_network']) : '';
            if (!in_array($net, array('algorand_mainnet', 'voi_mainnet', 'hedera_mainnet', 'stellar_mainnet'), true)) {
                wc_add_notice('Please select a network (Algorand, VOI, Hedera or Stellar) to continue.', 'error');
                return false;
            }
            return true;
        }

        public function process_payment($order_id) {
            $order    = wc_get_order($order_id);
            $api_base = $this->get_option('api_base', 'https://api1.ilovechicken.co.uk');
            $api_key  = $this->get_option('api_key');
            $tid      = $this->get_option('tenant_id');
            $network  = isset($_POST['algovoi_network']) ? sanitize_text_field($_POST['algovoi_network']) : 'algorand_mainnet';

            if (empty($api_key) || empty($tid)) { wc_add_notice('AlgoVoi not configured.', 'error'); return; }

            $label    = 'Order #' . $order->get_order_number();
            $redirect = $order->get_checkout_order_received_url();
            $result   = algovoi_create_link($api_base, $api_key, $tid, $order->get_total(), $order->get_currency(), $label, $network, $redirect);

            if (!$result) { wc_add_notice('Payment could not be initiated.', 'error'); return; }

            preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $result['checkout_url'], $tm);
            $order->update_meta_data('_algovoi_token',    isset($tm[1]) ? $tm[1] : $result['id']);
            $order->update_meta_data('_algovoi_api_base', $api_base);
            $order->update_meta_data('_algovoi_network',  $network);
            $order->save();

            $order->update_status('pending-payment', 'Awaiting AlgoVoi payment (' . $network . ').');
            wc_reduce_stock_levels($order_id);
            WC()->cart->empty_cart();
            return array('result' => 'success', 'redirect' => $result['checkout_url']);
        }
    }

    /* ════════════════════════════════════════════════════════════════════════
     * Gateway 2: AlgoVoi Browser Extension
     * ════════════════════════════════════════════════════════════════════════ */
    class WC_AlgoVoi_Extension_Gateway extends WC_Payment_Gateway {

        public function __construct() {
            $this->id = 'algovoi_extension'; $this->has_fields = true;
            $this->method_title = 'AlgoVoi Extension';
            $this->method_description = 'Pay instantly via the AlgoVoi browser extension (Algorand or VOI). No redirect.';
            $this->init_form_fields(); $this->init_settings();
            $this->title       = $this->get_option('title', 'AlgoVoi - Pay via Extension');
            $this->description = $this->get_option('description', 'Pay with USDC (Algorand) or aUSDC (VOI) via the AlgoVoi browser extension.');
            add_action('woocommerce_update_options_payment_gateways_' . $this->id, array($this, 'process_admin_options'));
            add_action('woocommerce_thankyou_' . $this->id, array($this, 'render_extension_payment_ui'));
        }

        public function init_form_fields() {
            $this->form_fields = array(
                'enabled'     => array('title' => 'Enable/Disable', 'type' => 'checkbox', 'label' => 'Enable AlgoVoi Extension', 'default' => 'yes'),
                'title'       => array('title' => 'Title',       'type' => 'text',     'default' => 'AlgoVoi - Pay via Extension'),
                'description' => array('title' => 'Description', 'type' => 'textarea', 'default' => 'Pay with USDC (Algorand) or aUSDC (VOI) via the AlgoVoi browser extension.'),
                'api_base'    => array('title' => 'API Base URL', 'type' => 'text',     'default' => 'https://api1.ilovechicken.co.uk'),
                'api_key'     => array('title' => 'API Key',     'type' => 'password', 'default' => ''),
                'tenant_id'   => array('title' => 'Tenant ID',   'type' => 'text',     'default' => ''),
            );
        }

        public function payment_fields() {
            if ($desc = $this->get_description())
                echo '<p style="margin:0 0 .5rem;color:#9ca3af;font-size:.9rem;">' . wp_kses_post($desc) . '</p>';
            algovoi_chain_selector_html('algovoi_ext_network');
        }

        public function validate_fields() {
            $net = isset($_POST['algovoi_ext_network']) ? sanitize_text_field($_POST['algovoi_ext_network']) : '';
            if (!in_array($net, array('algorand_mainnet', 'voi_mainnet'), true)) {
                wc_add_notice('Please select a network (Algorand or VOI) to continue.', 'error');
                return false;
            }
            return true;
        }

        public function process_payment($order_id) {
            $order    = wc_get_order($order_id);
            $api_base = $this->get_option('api_base', 'https://api1.ilovechicken.co.uk');
            $api_key  = $this->get_option('api_key');
            $tid      = $this->get_option('tenant_id');
            $network  = isset($_POST['algovoi_ext_network']) ? sanitize_text_field($_POST['algovoi_ext_network']) : 'algorand_mainnet';

            if (empty($api_key) || empty($tid)) { wc_add_notice('AlgoVoi not configured.', 'error'); return; }

            $label  = 'Order #' . $order->get_order_number();
            $result = algovoi_create_link($api_base, $api_key, $tid, $order->get_total(), $order->get_currency(), $label, $network);

            if (!$result) { wc_add_notice('Payment could not be initiated.', 'error'); return; }

            // Fetch receiver and memo from checkout page
            $checkout = algovoi_parse_checkout($result['checkout_url'], $api_base);
            if (!$checkout) { wc_add_notice('Could not load payment details.', 'error'); return; }

            $asset_id = (string) $result['asset_id'];
            $am       = isset(ALGOVOI_AM[$asset_id]) ? ALGOVOI_AM[$asset_id] : null;
            if (!$am) { wc_add_notice('Unsupported asset returned by server.', 'error'); return; }

            preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $result['checkout_url'], $tm);
            $order->update_meta_data('_algovoi_token',    isset($tm[1]) ? $tm[1] : $result['id']);
            $order->update_meta_data('_algovoi_api_base', $api_base);
            $order->update_meta_data('_algovoi_checkout_url',   $result['checkout_url']);
            $order->update_meta_data('_algovoi_receiver',       $checkout['receiver']);
            $order->update_meta_data('_algovoi_memo',           $checkout['memo']);
            $order->update_meta_data('_algovoi_amount_display', number_format($result['amount_microunits'] / pow(10, $am['dec']), 2));
            $order->update_meta_data('_algovoi_ticker',         $am['ticker']);
            $order->update_meta_data('_algovoi_asset_id',       (int) $asset_id);
            $order->update_meta_data('_algovoi_microunits',     (int) $result['amount_microunits']);
            $order->update_meta_data('_algovoi_algod',          $am['algod']);
            $order->update_meta_data('_algovoi_chain',          $am['chain']);
            $order->update_meta_data('_algovoi_network',        $network);
            $order->save();

            $order->update_status('pending-payment', 'Awaiting AlgoVoi extension payment (' . $am['chain'] . ').');
            WC()->cart->empty_cart();
            return array('result' => 'success', 'redirect' => $this->get_return_url($order));
        }

        public function render_extension_payment_ui($order_id) {
            $order = wc_get_order($order_id);
            if (!$order || $order->get_payment_method() !== $this->id) return;
            if ($order->is_paid()) {
                echo '<div style="margin:1.5rem 0;padding:1rem;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.3);border-radius:8px;color:#10b981;">Payment received. Thank you!</div>';
                return;
            }
            $token    = $order->get_meta('_algovoi_token');
            $receiver = $order->get_meta('_algovoi_receiver');
            $memo     = $order->get_meta('_algovoi_memo');
            $amt      = $order->get_meta('_algovoi_amount_display');
            $ticker   = $order->get_meta('_algovoi_ticker');
            $asset_id = (int) $order->get_meta('_algovoi_asset_id');
            $mu       = (int) $order->get_meta('_algovoi_microunits');
            $algod    = $order->get_meta('_algovoi_algod');
            $co_url   = $order->get_meta('_algovoi_checkout_url');
            $chain    = $order->get_meta('_algovoi_chain');
            $network  = $order->get_meta('_algovoi_network');
            $api_base = $order->get_meta('_algovoi_api_base') ?: 'https://api1.ilovechicken.co.uk';
            $okey     = $order->get_order_key();
            $vurl     = rest_url('algovoi/v1/orders/' . $order_id . '/verify');
            if (!$token || !$receiver || !$memo) return;

            $am           = isset(ALGOVOI_AM[(string)$asset_id]) ? ALGOVOI_AM[(string)$asset_id] : array('colour' => '#3b82f6');
            $chain_colour = $am['colour'];
            $sa  = esc_html($amt . ' ' . $ticker);
            $sc  = esc_html($chain);
            $sco = esc_url($co_url);
            $jr  = wp_json_encode($receiver);
            $jm  = wp_json_encode($memo);
            $ja  = wp_json_encode(rtrim($algod, '/'));
            $jv  = wp_json_encode($vurl);
            $jk  = wp_json_encode($okey);
            ?>
<div id="av-ext-pay" style="margin:2rem 0;padding:1.5rem 1.75rem;background:#1e2130;border:1px solid #2a2d3a;border-radius:12px;color:#f1f2f6;font-family:system-ui,sans-serif;">
  <div style="font-size:.68rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#6b7280;margin-bottom:.85rem;">
    <span style="color:<?php echo esc_attr($chain_colour); ?>;">AlgoVoi</span>
    &middot; <?php echo $sc; ?> Extension Payment
  </div>
  <p style="margin:0 0 1.25rem;color:#9ca3af;font-size:.9rem;line-height:1.6;">
    Complete your order by sending <strong style="color:#10b981;"><?php echo $sa; ?></strong>
    on <strong style="color:#f1f2f6;"><?php echo $sc; ?></strong> via the AlgoVoi browser extension.
  </p>
  <div id="av-no-ext" style="display:none;margin-bottom:1rem;padding:.75rem 1rem;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:8px;font-size:.85rem;color:#ef4444;">
    AlgoVoi extension not detected.
    <a href="<?php echo $sco; ?>" target="_blank" rel="noopener" style="color:#3b82f6;">Pay manually &rarr;</a>
  </div>
  <div id="av-msg" style="display:none;margin-bottom:.85rem;padding:.65rem .9rem;border-radius:8px;font-size:.85rem;"></div>
  <button id="av-pay-btn" onclick="avPayWithExtension()"
    style="display:inline-flex;align-items:center;gap:.5rem;padding:.8rem 1.6rem;background:<?php echo esc_attr($chain_colour); ?>;color:#fff;border:none;border-radius:8px;font-size:.95rem;font-weight:600;cursor:pointer;">
    &#9889; Pay <?php echo $sa; ?> via Extension
  </button>
  <p style="margin:.85rem 0 0;font-size:.75rem;color:#6b7280;">
    No extension? <a href="<?php echo $sco; ?>" target="_blank" rel="noopener" style="color:#3b82f6;">Pay on the hosted checkout page</a> instead.
  </p>
</div>
<script src="https://cdn.jsdelivr.net/npm/algosdk@2/dist/browser/algosdk.min.js"></script>
<script>
(function () {
  var AV = {
    receiver:   <?php echo $jr; ?>,
    memo:       <?php echo $jm; ?>,
    microunits: <?php echo $mu; ?>,
    assetId:    <?php echo $asset_id; ?>,
    algodUrl:   <?php echo $ja; ?>,
    verifyUrl:  <?php echo $jv; ?>,
    orderKey:   <?php echo $jk; ?>,
  };
  function showMsg(h, t) {
    var e = document.getElementById('av-msg');
    e.innerHTML = h; e.style.display = 'block';
    e.style.background = t==='ok' ? 'rgba(16,185,129,.1)' : 'rgba(239,68,68,.1)';
    e.style.border     = t==='ok' ? '1px solid rgba(16,185,129,.3)' : '1px solid rgba(239,68,68,.3)';
    e.style.color      = t==='ok' ? '#10b981' : '#ef4444';
  }
  function setBtn(txt, dis) {
    var b = document.getElementById('av-pay-btn');
    if (!b) return; b.textContent = txt; b.disabled = !!dis; b.style.opacity = dis ? '.6' : '1';
  }
  function u8b64(a) { var s=''; for(var i=0;i<a.length;i++) s+=String.fromCharCode(a[i]); return btoa(s); }
  window.avPayWithExtension = async function () {
    try {
      setBtn('Connecting\u2026', true);
      if (!window.algorand || !window.algorand.isAlgoVoi) {
        document.getElementById('av-no-ext').style.display = 'block';
        document.getElementById('av-pay-btn').style.display = 'none';
        return;
      }
      setBtn('Fetching params\u2026', true);
      var algodClient = new algosdk.Algodv2('', AV.algodUrl, '');
      var sp = await algodClient.getTransactionParams().do();
      setBtn('Connecting wallet\u2026', true);
      var er = await window.algorand.enable({ genesisHash: sp.genesisHash });
      if (!er.accounts || !er.accounts.length) throw new Error('No accounts returned. Check your wallet.');
      var sender = er.accounts[0];
      setBtn('Building tx\u2026', true);
      var nb  = new TextEncoder().encode(AV.memo);
      // Both Algorand (ASA 31566704) and VOI (ASA 302190) use native ASA transfers
      var txn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
        from: sender, to: AV.receiver, assetIndex: AV.assetId,
        amount: AV.microunits, note: nb, suggestedParams: sp,
      });
      setBtn('Sign & send\u2026', true);
      var res = await window.algorand.signAndSendTransactions({ txns: [{ txn: u8b64(txn.toByte()) }] });
      if (!res.stxns || !res.stxns[0]) throw new Error('Extension did not return signed transaction.');
      var stxnBytes = Uint8Array.from(atob(res.stxns[0]), function(c) { return c.charCodeAt(0); });
      setBtn('Submitting\u2026', true);
      var submitResp = await fetch(AV.algodUrl + '/v2/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-binary' },
        body: stxnBytes,
      });
      var submitData = await submitResp.json();
      if (!submitResp.ok) throw new Error('Algod submission failed: ' + (submitData.message || submitResp.status));
      var txId = submitData.txId;
      if (!txId) throw new Error('No txId in algod response: ' + JSON.stringify(submitData));
      setBtn('Waiting for confirmation\u2026', true);
      var confirmedRound = 0;
      for (var attempt = 0; attempt < 20; attempt++) {
        await new Promise(function(r) { setTimeout(r, 3000); });
        var pendingResp = await fetch(AV.algodUrl + '/v2/transactions/pending/' + encodeURIComponent(txId));
        if (pendingResp.status === 404) { confirmedRound = 1; break; }
        var pendingData = await pendingResp.json();
        if (pendingData['confirmed-round'] && pendingData['confirmed-round'] > 0) {
          confirmedRound = pendingData['confirmed-round']; break;
        }
        if (pendingData['pool-error'] && pendingData['pool-error'].length > 0)
          throw new Error('Transaction rejected by network: ' + pendingData['pool-error']);
      }
      if (!confirmedRound) throw new Error('Transaction not confirmed after timeout. TX: ' + txId);
      await new Promise(function(r) { setTimeout(r, 4000); });
      setBtn('Verifying\u2026', true);
      var vr = await fetch(AV.verifyUrl, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tx_id: txId, order_key: AV.orderKey }),
      });
      var vd = await vr.json();
      if (vr.ok && vd.success) {
        showMsg('\u2713 Payment verified! Refreshing\u2026', 'ok');
        setBtn('Paid \u2713', true);
        setTimeout(function () { location.reload(); }, 2000);
      } else {
        throw new Error(vd.detail || vd.message || 'Verification failed. Please try again.');
      }
    } catch (err) {
      showMsg('&#9888; ' + err.message, 'err');
      setBtn('\u26a1 Retry', false);
    }
  };
  window.addEventListener('load', function () {
    setTimeout(function () {
      if (!window.algorand || !window.algorand.isAlgoVoi)
        document.getElementById('av-no-ext').style.display = 'block';
    }, 700);
  });
})();
</script>
<?php
        }
    }
});
