<?php
/**
 * Plugin Name: AlgoVoi Payment Gateway
 * Description: Hosted checkout and browser-extension payment on Algorand and VOI.
 * Version: 2.0.0
 * Requires Plugins: woocommerce
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
    if (!$tx_id) return new WP_Error('missing_tx', 'tx_id required', array('status' => 400));
    $order = wc_get_order($order_id);
    if (!$order || $order->get_order_key() !== $order_key)
        return new WP_Error('not_found', 'Order not found', array('status' => 404));
    if ($order->is_paid())
        return new WP_REST_Response(array('success' => true, 'already_paid' => true), 200);
    $token = $order->get_meta('_algovoi_token');
    if (!$token) return new WP_Error('no_token', 'No AlgoVoi token', array('status' => 400));
    $vurl = 'https://api1.ilovechicken.co.uk/checkout/' . rawurlencode($token) . '/verify';
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

add_action('plugins_loaded', function () {
    if (!class_exists('WC_Payment_Gateway')) return;

    // Gateway 1: Hosted checkout redirect
    class WC_AlgoVoi_Gateway extends WC_Payment_Gateway {
        public function __construct() {
            $this->id = 'algovoi'; $this->has_fields = false;
            $this->method_title = 'AlgoVoi';
            $this->method_description = 'USDC (Algorand) or aUSDC (VOI) via hosted checkout.';
            $this->init_form_fields(); $this->init_settings();
            $this->title       = $this->get_option('title', 'AlgoVoi - Pay with Crypto');
            $this->description = $this->get_option('description', 'Pay with USDC on Algorand or aUSDC on VOI. You will be redirected to a secure hosted checkout.');
            add_action('woocommerce_update_options_payment_gateways_' . $this->id, array($this, 'process_admin_options'));
        }
        public function init_form_fields() {
            $this->form_fields = array(
                'enabled'        => array('title' => 'Enable/Disable', 'type' => 'checkbox', 'label' => 'Enable AlgoVoi', 'default' => 'yes'),
                'title'          => array('title' => 'Title', 'type' => 'text', 'default' => 'AlgoVoi - Pay with Crypto (USDC/aUSDC)'),
                'description'    => array('title' => 'Description', 'type' => 'textarea', 'default' => 'Pay with USDC on Algorand or aUSDC on VOI.'),
                'webhook_url'    => array('title' => 'Webhook URL', 'type' => 'text', 'default' => 'https://api1.ilovechicken.co.uk/webhooks/woocommerce/96eb0225-dd47-4bc3-be10-143d6e6d7bd1'),
                'webhook_secret' => array('title' => 'Webhook Secret', 'type' => 'password', 'default' => '_4bzgeF8sZ_1nORzudiiCCOrPi6u8UHtg57d1LXZzbA'),
            );
        }
        public function process_payment($order_id) {
            $order   = wc_get_order($order_id);
            $wh_url  = $this->get_option('webhook_url');
            $wh_sec  = $this->get_option('webhook_secret');
            if (empty($wh_url) || empty($wh_sec)) { wc_add_notice('AlgoVoi not configured.', 'error'); return; }
            $items = array();
            foreach ($order->get_items() as $item)
                $items[] = array('name' => $item->get_name(), 'quantity' => $item->get_quantity());
            $payload = wp_json_encode(array(
                'id' => $order_id, 'status' => 'pending',
                'currency' => $order->get_currency(), 'total' => $order->get_total(),
                'order_key' => $order->get_order_key(),
                'billing'   => array('email' => $order->get_billing_email(), 'first_name' => $order->get_billing_first_name(), 'last_name' => $order->get_billing_last_name()),
                'line_items' => $items,
            ));
            $sig  = base64_encode(hash_hmac('sha256', $payload, $wh_sec, true));
            $resp = wp_remote_post($wh_url, array(
                'timeout' => 30, 'sslverify' => true,
                'headers' => array('Content-Type' => 'application/json', 'X-WC-Webhook-Signature' => $sig, 'X-WC-Webhook-Topic' => 'order.created', 'X-WC-Webhook-Source' => home_url('/')),
                'body' => $payload,
            ));
            if (is_wp_error($resp)) { wc_add_notice('Error: ' . $resp->get_error_message(), 'error'); return; }
            $code = wp_remote_retrieve_response_code($resp);
            $body = json_decode(wp_remote_retrieve_body($resp), true);
            if ($code !== 200 || empty($body['checkout_url'])) { wc_add_notice('Payment could not be initiated.', 'error'); return; }
            $order->update_status('pending-payment', 'Awaiting AlgoVoi payment.');
            wc_reduce_stock_levels($order_id);
            WC()->cart->empty_cart();
            return array('result' => 'success', 'redirect' => $body['checkout_url']);
        }
    }

    // Gateway 2: AlgoVoi Browser Extension
    class WC_AlgoVoi_Extension_Gateway extends WC_Payment_Gateway {
        // Receiver address → ASA/app ID mapping — configure in WP admin settings.
        // Do not hardcode live wallet addresses here.
        private static $R2A = array();
        private static $AM = array(
            '31566704' => array('ticker' => 'USDC',  'dec' => 6, 'algod' => 'https://mainnet-api.algonode.cloud', 'chain' => 'Algorand'),
            '302190'   => array('ticker' => 'aUSDC', 'dec' => 6, 'algod' => 'https://mainnet-api.voi.nodely.io',  'chain' => 'VOI'),
        );
        public function __construct() {
            $this->id = 'algovoi_extension'; $this->has_fields = false;
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
                'enabled'        => array('title' => 'Enable/Disable', 'type' => 'checkbox', 'label' => 'Enable AlgoVoi Extension', 'default' => 'yes'),
                'title'          => array('title' => 'Title', 'type' => 'text', 'default' => 'AlgoVoi - Pay via Extension'),
                'description'    => array('title' => 'Description', 'type' => 'textarea', 'default' => 'Pay with USDC (Algorand) or aUSDC (VOI) via the AlgoVoi browser extension.'),
                'webhook_url'    => array('title' => 'Webhook URL', 'type' => 'text', 'default' => 'https://api1.ilovechicken.co.uk/webhooks/woocommerce/96eb0225-dd47-4bc3-be10-143d6e6d7bd1'),
                'webhook_secret' => array('title' => 'Webhook Secret', 'type' => 'password', 'default' => '_4bzgeF8sZ_1nORzudiiCCOrPi6u8UHtg57d1LXZzbA'),
            );
        }
        private function _webhook($order) {
            $wh_url = $this->get_option('webhook_url'); $wh_sec = $this->get_option('webhook_secret');
            $items  = array();
            foreach ($order->get_items() as $item)
                $items[] = array('name' => $item->get_name(), 'quantity' => $item->get_quantity());
            $pl  = wp_json_encode(array(
                'id' => $order->get_id(), 'status' => 'pending',
                'currency' => $order->get_currency(), 'total' => $order->get_total(),
                'order_key' => $order->get_order_key(),
                'billing'   => array('email' => $order->get_billing_email(), 'first_name' => $order->get_billing_first_name(), 'last_name' => $order->get_billing_last_name()),
                'line_items' => $items,
            ));
            $sig = base64_encode(hash_hmac('sha256', $pl, $wh_sec, true));
            $r   = wp_remote_post($wh_url, array(
                'timeout' => 30, 'sslverify' => true,
                'headers' => array('Content-Type' => 'application/json', 'X-WC-Webhook-Signature' => $sig, 'X-WC-Webhook-Topic' => 'order.created', 'X-WC-Webhook-Source' => home_url('/')),
                'body' => $pl,
            ));
            if (is_wp_error($r)) { wc_get_logger()->error('AlgoVoi ext: ' . $r->get_error_message(), array('source' => 'algovoi-ext')); return null; }
            $code = wp_remote_retrieve_response_code($r);
            $body = json_decode(wp_remote_retrieve_body($r), true);
            if ($code !== 200 || empty($body['checkout_url'])) { wc_get_logger()->error('AlgoVoi ext HTTP ' . $code, array('source' => 'algovoi-ext')); return null; }
            return $body['checkout_url'];
        }
        private function _parse($url) {
            $r = wp_remote_get($url, array('timeout' => 15, 'sslverify' => true));
            if (is_wp_error($r) || wp_remote_retrieve_response_code($r) !== 200) return null;
            $html = wp_remote_retrieve_body($r);
            if (!preg_match('/<div[^>]+id=["\']addr["\'][^>]*>([A-Z2-7]{58})</', $html, $m)) return null;
            $rcv = $m[1];
            if (!preg_match('/<div[^>]+id=["\']memo["\'][^>]*>(algovoi:[^<]+)</', $html, $m)) return null;
            $memo = trim($m[1]);
            if (!preg_match('/<div class="amount"[^>]*>\s*([\d.]+)<span class="ticker">([^<]+)<\/span>/', $html, $m)) return null;
            $amt = $m[1]; $tick = trim($m[2]);
            $aid = isset(self::$R2A[$rcv]) ? self::$R2A[$rcv] : null;
            if (!$aid) { wc_get_logger()->error('AlgoVoi ext: unknown rcv ' . $rcv, array('source' => 'algovoi-ext')); return null; }
            $meta = self::$AM[$aid];
            return array(
                'receiver' => $rcv, 'memo' => $memo, 'amount_display' => $amt, 'ticker' => $tick,
                'asset_id' => (int)$aid, 'microunits' => (int)round((float)$amt * pow(10, $meta['dec'])),
                'algod' => $meta['algod'], 'chain' => $meta['chain'],
            );
        }
        public function process_payment($order_id) {
            $order = wc_get_order($order_id);
            $url   = $this->_webhook($order);
            if (!$url) { wc_add_notice('Payment could not be initiated.', 'error'); return null; }
            if (!preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $url, $m)) { wc_add_notice('Unexpected payment URL.', 'error'); return null; }
            $token = $m[1];
            $p = $this->_parse($url);
            if (!$p) { wc_add_notice('Could not load payment details.', 'error'); return null; }
            $order->update_meta_data('_algovoi_token',        $token);
            $order->update_meta_data('_algovoi_checkout_url', $url);
            $order->update_meta_data('_algovoi_receiver',     $p['receiver']);
            $order->update_meta_data('_algovoi_memo',         $p['memo']);
            $order->update_meta_data('_algovoi_amount_display',$p['amount_display']);
            $order->update_meta_data('_algovoi_ticker',       $p['ticker']);
            $order->update_meta_data('_algovoi_asset_id',     $p['asset_id']);
            $order->update_meta_data('_algovoi_microunits',   $p['microunits']);
            $order->update_meta_data('_algovoi_algod',        $p['algod']);
            $order->update_meta_data('_algovoi_chain',        $p['chain']);
            $order->save();
            $order->update_status('pending-payment', 'Awaiting AlgoVoi extension payment.');
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
            $okey     = $order->get_order_key();
            $vurl     = rest_url('algovoi/v1/orders/' . $order_id . '/verify');
            if (!$token || !$receiver || !$memo) return;
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
    <span style="color:#3b82f6;">AlgoVoi</span> &middot; Extension Payment
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
    style="display:inline-flex;align-items:center;gap:.5rem;padding:.8rem 1.6rem;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-size:.95rem;font-weight:600;cursor:pointer;">
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
      // Use algosdk's own Algodv2 client so suggestedParams is the correctly-typed object algosdk expects
      var algodClient = new algosdk.Algodv2('', AV.algodUrl, '');
      var sp = await algodClient.getTransactionParams().do();
      setBtn('Connecting wallet\u2026', true);
      var er = await window.algorand.enable({ genesisHash: sp.genesisHash });
      if (!er.accounts || !er.accounts.length) throw new Error('No accounts returned. Check your wallet.');
      var sender = er.accounts[0];
      setBtn('Building tx\u2026', true);
      var nb  = new TextEncoder().encode(AV.memo);
      var txn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
        from: sender, to: AV.receiver, assetIndex: AV.assetId,
        amount: AV.microunits, note: nb, suggestedParams: sp,
      });
      setBtn('Sign & send\u2026', true);
      // signAndSendTransactions signs but defers submission — txnIDs is [].
      // We take the signed bytes (stxns) and submit to algod ourselves.
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

      // Wait for on-chain confirmation before calling AlgoVoi verify (indexer lag)
      setBtn('Waiting for confirmation\u2026', true);
      var confirmedRound = 0;
      for (var attempt = 0; attempt < 20; attempt++) {
        await new Promise(function(r) { setTimeout(r, 3000); });
        var pendingResp = await fetch(AV.algodUrl + '/v2/transactions/pending/' + encodeURIComponent(txId));
        if (pendingResp.status === 404) { confirmedRound = 1; break; } // gone from mempool = confirmed
        var pendingData = await pendingResp.json();
        if (pendingData['confirmed-round'] && pendingData['confirmed-round'] > 0) {
          confirmedRound = pendingData['confirmed-round']; break;
        }
        if (pendingData['pool-error'] && pendingData['pool-error'].length > 0) {
          throw new Error('Transaction rejected by network: ' + pendingData['pool-error']);
        }
      }
      if (!confirmedRound) throw new Error('Transaction not confirmed after timeout. TX: ' + txId);
      // Extra pause for indexer to catch up
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
