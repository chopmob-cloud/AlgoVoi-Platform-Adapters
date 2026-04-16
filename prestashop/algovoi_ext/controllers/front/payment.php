<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
class Algovoi_ExtPaymentModuleFrontController extends ModuleFrontController
{
    private const ALGOD = [
        'algorand-mainnet' => ['url' => 'https://mainnet-api.algonode.cloud', 'asset_id' => 31566704, 'ticker' => 'USDC',  'dec' => 6],
        'voi-mainnet'      => ['url' => 'https://mainnet-api.voi.nodely.io',  'asset_id' => 302190,   'ticker' => 'aUSDC', 'dec' => 6],
    ];

    public function initContent()
    {
        parent::initContent();

        $cart = $this->context->cart;
        if (!$cart->id || $cart->id_customer == 0 || !Validate::isLoadedObject($this->context->customer)) {
            Tools::redirect('index.php?controller=order&step=1');
        }

        $api_base = rtrim(Configuration::get('ALGOVOI_EXT_API_BASE_URL'), '/');
        $api_key  = Configuration::get('ALGOVOI_EXT_API_KEY');
        $tenant   = Configuration::get('ALGOVOI_EXT_TENANT_ID');
        $network  = Tools::getValue('algovoi_ext_network') ?: 'algorand_mainnet';
        $allowed  = ['algorand_mainnet', 'voi_mainnet'];
        if (!in_array($network, $allowed, true)) $network = 'algorand_mainnet';

        $currency = new Currency($cart->id_currency);
        $total    = (float)$cart->getOrderTotal(true, Cart::BOTH);
        $label    = 'Order #' . (int)$cart->id;

        // Create payment link
        $payload = json_encode([
            'amount'            => round($total, 2),
            'currency'          => $currency->iso_code,
            'label'             => $label,
            'preferred_network' => $network,
        ]);

        $ch = curl_init($api_base . '/v1/payment-links');
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_SSL_VERIFYPEER => true,   // FIX: explicit SSL verification
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $api_key,
                'X-Tenant-Id: ' . $tenant,
            ],
        ]);
        $response  = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        $body = json_decode($response, true);

        if (($http_code !== 200 && $http_code !== 201) || empty($body['checkout_url'])) {
            $this->errors[] = $this->module->l('Could not create payment request. Please try again.');
            $this->redirectWithNotifications($this->context->link->getPageLink('order', true, null, ['step' => 3]));
            return;
        }

        $checkout_url = $body['checkout_url'];
        $chain        = $body['chain'] ?? 'algorand-mainnet';
        $amount_mu    = (int)($body['amount_microunits'] ?? 0);
        $algod_cfg    = self::ALGOD[$chain] ?? self::ALGOD['algorand-mainnet'];

        // SSRF guard: checkout URL must be on the same host as api_base
        $api_host      = parse_url($api_base, PHP_URL_HOST);
        $checkout_host = parse_url($checkout_url, PHP_URL_HOST);
        if (!$api_host || $checkout_host !== $api_host) {
            $this->errors[] = $this->module->l('Payment configuration error. Please try again.');
            $this->redirectWithNotifications($this->context->link->getPageLink('order', true, null, ['step' => 3]));
            return;
        }

        // Scrape checkout page for receiver and memo
        $ch2 = curl_init($checkout_url);
        curl_setopt_array($ch2, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_SSL_VERIFYPEER => true,   // FIX: explicit SSL verification
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);
        $html = curl_exec($ch2);
        curl_close($ch2);

        $receiver = $memo = '';
        if ($html) {
            // Match: onclick="copyText('ADDR58CHARS', this)" — address is the first 58-char base32 value
            if (preg_match('/onclick="copyText\(\'([A-Z2-7]{58})\'/', $html, $m)) {
                $receiver = $m[1];
            }
            // Match: onclick="copyText('algovoi:TOKEN', this)"
            if (preg_match('/onclick="copyText\(\'(algovoi:[A-Za-z0-9_-]+)\'/', $html, $m)) {
                $memo = $m[1];
            }
        }

        if (!$receiver || !$memo) {
            $this->errors[] = $this->module->l('Could not load payment details. Please try again.');
            $this->redirectWithNotifications($this->context->link->getPageLink('order', true, null, ['step' => 3]));
            return;
        }

        // Extract short token from checkout URL
        $token = '';
        if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $checkout_url, $m)) {
            $token = $m[1];
        }

        // Create order in pending state
        $this->module->validateOrder(
            $cart->id,
            (int)Configuration::get('ALGOVOI_EXT_PENDING_STATUS') ?: 1,
            $total,
            $this->module->displayName,
            'AlgoVoi checkout token: ' . $token,
            ['transaction_id' => $token],
            (int)$cart->id_currency,
            false,
            $this->context->customer->secure_key
        );

        $order_id = (int)Order::getIdByCartId($cart->id);

        // Store token and order_id in session cookie
        $this->context->cookie->__set('algovoi_token',    $token);
        $this->context->cookie->__set('algovoi_order_id', (string)$order_id);
        $this->context->cookie->write();

        $chain_display = ($algod_cfg['ticker'] === 'aUSDC') ? 'VOI' : 'Algorand';

        $this->context->smarty->assign([
            'algovoi_receiver'     => $receiver,
            'algovoi_memo'         => $memo,
            'algovoi_amount_mu'    => $amount_mu,
            'algovoi_asset_id'     => $algod_cfg['asset_id'],
            'algovoi_algod_url'    => $algod_cfg['url'],
            'algovoi_ticker'       => $algod_cfg['ticker'],
            'algovoi_amount'       => number_format($amount_mu / pow(10, $algod_cfg['dec']), 2),
            'algovoi_chain'        => $chain_display,
            'algovoi_checkout_url' => $checkout_url,
            'algovoi_verify_url'   => $this->context->link->getModuleLink('algovoi_ext', 'verify', [], true),
            'algovoi_success_url'  => $this->context->link->getPageLink('order-confirmation', true, null, [
                'id_cart'   => $cart->id,
                'id_module' => $this->module->id,
                'key'       => $this->context->customer->secure_key,
            ]),
        ]);

        $this->setTemplate('module:algovoi_ext/views/templates/front/pending.tpl');
    }
}
