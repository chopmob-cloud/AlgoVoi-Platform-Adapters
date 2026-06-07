<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
namespace Opencart\Catalog\Controller\Extension\AlgovoiExt\Payment;

class AlgovoiExt extends \Opencart\System\Engine\Controller {

    private const ALGOD = [
        'algorand-mainnet' => ['url' => 'https://mainnet-api.algonode.cloud', 'asset_id' => 31566704, 'ticker' => 'USDC',  'dec' => 6],
        'voi-mainnet'      => ['url' => 'https://mainnet-api.voi.nodely.io',  'asset_id' => 302190,   'ticker' => 'aUSDC', 'dec' => 6],
    ];

    public function index(): string {
        $this->load->language('extension/algovoi_ext/payment/algovoi_ext');
        $data['language'] = $this->config->get('config_language');
        return $this->load->view('extension/algovoi_ext/payment/algovoi_ext', $data);
    }

    public function confirm(): void {
        $this->load->language('extension/algovoi_ext/payment/algovoi_ext');
        $json = [];

        if (!isset($this->session->data['order_id'])) {
            $json['redirect'] = $this->url->link('checkout/failure', 'language=' . $this->config->get('config_language'), true);
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode($json));
            return;
        }

        $this->load->model('checkout/order');
        $order = $this->model_checkout_order->getOrder($this->session->data['order_id']);

        if (!$order) {
            $json['redirect'] = $this->url->link('checkout/failure', 'language=' . $this->config->get('config_language'), true);
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode($json));
            return;
        }

        $tenant_id = $this->config->get('payment_algovoi_tenant_id');
        $api_key   = $this->config->get('payment_algovoi_admin_api_key');
        // FIX: use trim() not db->escape() for non-SQL data; whitelist is the real guard
        $network   = isset($_POST['algovoi_ext_network']) ? trim($_POST['algovoi_ext_network']) : ($this->config->get('payment_algovoi_preferred_network') ?: 'algorand_mainnet');
        $allowed   = ['algorand_mainnet', 'voi_mainnet'];
        if (!in_array($network, $allowed, true)) $network = 'algorand_mainnet';

        // Create payment link
        $payload = json_encode([
            'amount'             => round((float)$order['total'], 2),
            'currency'           => strtoupper($order['currency_code']),
            'label'              => 'Order #' . $order['order_id'],
            'preferred_network'  => $network,
            'redirect_url'       => $this->url->link('checkout/success', 'language=' . $this->config->get('config_language'), true),
            'expires_in_seconds' => 3600,
        ]);

        $api_base = rtrim($this->config->get('payment_algovoi_api_base_url') ?: 'https://cloud.algovoi.co.uk', '/');
        $ch = curl_init($api_base . '/v1/payment-links');
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_SSL_VERIFYPEER => true,    // FIX: explicit SSL verification
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $api_key,
                'X-Tenant-Id: ' . $tenant_id,
            ],
        ]);
        $response  = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $link = json_decode($response, true);

        if (($http_code !== 200 && $http_code !== 201) || empty($link['checkout_url'])) {
            $json['error'] = $this->language->get('error_payment_failed');
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode($json));
            return;
        }

        $checkout_url = $link['checkout_url'];
        $chain        = $link['chain'] ?? 'algorand-mainnet';
        $amount_mu    = (int)($link['amount_microunits'] ?? 0);

        // Determine algod config from chain
        $algod_cfg = self::ALGOD[$chain] ?? self::ALGOD['algorand-mainnet'];
        $asset_id  = $algod_cfg['asset_id'];
        $algod_url = $algod_cfg['url'];
        $ticker    = $algod_cfg['ticker'];
        $dec       = $algod_cfg['dec'];
        $amount_display = number_format($amount_mu / pow(10, $dec), 2);

        // SSRF guard: checkout URL must be on the same host as api_base
        $api_host      = parse_url($api_base, PHP_URL_HOST);
        $checkout_host = parse_url($checkout_url, PHP_URL_HOST);
        if (!$api_host || $checkout_host !== $api_host) {
            $json['error'] = $this->language->get('error_payment_failed');
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode($json));
            return;
        }

        // Scrape checkout page for receiver address and memo
        $ch2 = curl_init($checkout_url);
        curl_setopt_array($ch2, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);
        $html = curl_exec($ch2);
        curl_close($ch2);

        $receiver = '';
        $memo     = '';

        if ($html) {
            if (preg_match('/onclick="copyText\(\'([A-Z2-7]{58})\'/', $html, $m)) {
                $receiver = $m[1];
            }
            if (preg_match('/onclick="copyText\(\'(algovoi:[A-Za-z0-9_-]+)\'/', $html, $m)) {
                $memo = $m[1];
            }
        }

        if (!$receiver || !$memo) {
            $json['error'] = $this->language->get('error_payment_failed');
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode($json));
            return;
        }

        // Extract token from checkout URL
        $token = '';
        if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $checkout_url, $m)) {
            $token = $m[1];
        }

        // Store payment details in session
        $this->session->data['algovoi_ext'] = [
            'order_id'       => $this->session->data['order_id'],
            'token'          => $token,
            'checkout_url'   => $checkout_url,
            'receiver'       => $receiver,
            'memo'           => $memo,
            'amount_display' => $amount_display,
            'ticker'         => $ticker,
            'asset_id'       => $asset_id,
            'amount_mu'      => $amount_mu,
            'algod_url'      => $algod_url,
            'chain'          => $chain,
        ];

        $pending_status = (int)$this->config->get('payment_algovoi_pending_status_id') ?: 1;
        $this->model_checkout_order->addHistory(
            $this->session->data['order_id'],
            $pending_status,
            'Awaiting AlgoVoi extension payment',
            false
        );

        $json['redirect'] = $this->url->link('extension/algovoi_ext/payment/algovoi_ext.pending', 'language=' . $this->config->get('config_language'), true);

        $this->response->addHeader('Content-Type: application/json');
        $this->response->setOutput(json_encode($json));
    }

    public function pending(): void {
        if (empty($this->session->data['algovoi_ext'])) {
            $this->response->redirect($this->url->link('checkout/cart', 'language=' . $this->config->get('config_language'), true));
            return;
        }

        $p = $this->session->data['algovoi_ext'];

        $verify_url  = $this->url->link('extension/algovoi_ext/payment/algovoi_ext.verify', 'language=' . $this->config->get('config_language'), true);
        $success_url = $this->url->link('checkout/success', 'language=' . $this->config->get('config_language'), true);

        $data['title']       = 'Complete Payment';
        $data['heading_title'] = 'Complete Your Payment';
        $data['amount']      = $p['amount_display'] . ' ' . $p['ticker'];
        $data['chain']       = $p['chain'];
        $data['checkout_url'] = $p['checkout_url'];
        $data['receiver']    = htmlspecialchars($p['receiver']);
        $data['memo']        = htmlspecialchars($p['memo']);
        $data['asset_id']    = (int)$p['asset_id'];
        $data['amount_mu']   = (int)$p['amount_mu'];
        $data['algod_url']   = htmlspecialchars($p['algod_url']);
        $data['verify_url']  = $verify_url;
        $data['success_url'] = $success_url;
        $data['language']    = $this->config->get('config_language');

        $data['column_left']    = $this->load->controller('common/column_left');
        $data['column_right']   = $this->load->controller('common/column_right');
        $data['content_top']    = $this->load->controller('common/content_top');
        $data['content_bottom'] = $this->load->controller('common/content_bottom');
        $data['footer']         = $this->load->controller('common/footer');
        $data['header']         = $this->load->controller('common/header');

        $this->response->setOutput($this->load->view('extension/algovoi_ext/payment/algovoi_ext_pending', $data));
    }

    public function verify(): void {
        $json = [];

        $input = json_decode(file_get_contents('php://input'), true);
        $tx_id = isset($input['tx_id']) ? trim($input['tx_id']) : '';

        // FIX: basic length guard on tx_id
        if (!$tx_id || strlen($tx_id) > 200 || empty($this->session->data['algovoi_ext']['token'])) {
            $this->response->addHeader('Content-Type: application/json');
            $this->response->setOutput(json_encode(['error' => 'Missing tx_id or session expired.']));
            return;
        }

        $token    = $this->session->data['algovoi_ext']['token'];
        $order_id = $this->session->data['algovoi_ext']['order_id'];

        $api_base = rtrim($this->config->get('payment_algovoi_api_base_url') ?: 'https://cloud.algovoi.co.uk', '/');
        $ch = curl_init($api_base . '/checkout/' . rawurlencode($token) . '/verify');
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode(['tx_id' => $tx_id]),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_SSL_VERIFYPEER => true,   // FIX: explicit SSL verification
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        ]);
        $response  = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $body = json_decode($response, true);

        if ($http_code === 200) {
            $this->load->model('checkout/order');
            $complete_status = (int)$this->config->get('payment_algovoi_complete_status_id') ?: 5;
            $this->model_checkout_order->addHistory(
                $order_id,
                $complete_status,
                'AlgoVoi extension payment confirmed. TX: ' . $tx_id,
                true
            );
            unset($this->session->data['algovoi_ext']);
            $json['success'] = true;
        } else {
            $detail = $body['detail'] ?? $body['message'] ?? 'Verification failed.';
            $json['error'] = $detail;
        }

        $this->response->addHeader('Content-Type: application/json');
        $this->response->setOutput(json_encode($json));
    }

    public function webhook(): void {
        $raw_body = file_get_contents('php://input');
        $secret   = $this->config->get('payment_algovoi_webhook_secret');

        // FIX: reject immediately if webhook secret is not configured
        if (empty($secret)) {
            http_response_code(500);
            exit('Webhook secret not configured');
        }

        $sig_header = $_SERVER['HTTP_X_ALGOVOI_SIGNATURE'] ?? '';
        $expected   = base64_encode(hash_hmac('sha256', $raw_body, $secret, true));
        if (!hash_equals($expected, $sig_header)) {
            http_response_code(401);
            exit('Unauthorized');
        }

        $data = json_decode($raw_body, true);
        if (empty($data['order_id'])) {
            http_response_code(400);
            exit('Bad Request');
        }

        $this->load->model('checkout/order');
        $order = $this->model_checkout_order->getOrder((int)$data['order_id']);

        if ($order && in_array($order['order_status_id'], [1, 2])) {
            $complete_status = (int)$this->config->get('payment_algovoi_complete_status_id') ?: 5;
            $this->model_checkout_order->addHistory(
                (int)$data['order_id'],
                $complete_status,
                'AlgoVoi extension payment confirmed. TX: ' . ($data['tx_id'] ?? 'n/a'),
                true
            );
        }

        http_response_code(200);
        echo json_encode(['status' => 'ok']);
        exit;
    }
}
