<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
namespace Opencart\Catalog\Controller\Extension\Algovoi\Payment;

class Algovoi extends \Opencart\System\Engine\Controller {

    // All hosted networks with display labels
    private const ALL_NETWORKS = [
        'algorand_mainnet' => 'Algorand &mdash; USDC',
        'voi_mainnet'      => 'VOI &mdash; aUSDC',
        'hedera_mainnet'   => 'Hedera &mdash; USDC',
        'stellar_mainnet'  => 'Stellar &mdash; USDC',
        'base_mainnet'     => 'Base &mdash; USDC',
        'solana_mainnet'   => 'Solana &mdash; USDC',
        'tempo_mainnet'    => 'Tempo &mdash; USDC',
    ];

    private const NET_KEYS = [
        'algorand_mainnet' => 'algorand',
        'voi_mainnet'      => 'voi',
        'hedera_mainnet'   => 'hedera',
        'stellar_mainnet'  => 'stellar',
        'base_mainnet'     => 'base',
        'solana_mainnet'   => 'solana',
        'tempo_mainnet'    => 'tempo',
    ];

    public function index(): string {
        $this->load->language('extension/algovoi/payment/algovoi');
        $data['language'] = $this->config->get('config_language');

        // Build enabled_networks: default all enabled if config never saved
        $enabled = [];
        foreach (self::NET_KEYS as $net => $short) {
            $val = $this->config->get('payment_algovoi_net_' . $short);
            if ($val === null || $val === '' || $val === '1' || $val === 1) {
                $enabled[$net] = self::ALL_NETWORKS[$net];
            }
        }
        if (empty($enabled)) $enabled = self::ALL_NETWORKS;
        $data['enabled_networks'] = $enabled;

        return $this->load->view('extension/algovoi/payment/algovoi', $data);
    }

    public function confirm(): void {
        $this->load->language('extension/algovoi/payment/algovoi');
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
        // FIX: use trim() not db->escape() — this is API data, not SQL; whitelist is the real guard
        $network   = isset($_POST['algovoi_network']) ? trim($_POST['algovoi_network']) : ($this->config->get('payment_algovoi_preferred_network') ?: 'algorand_mainnet');
        $enabled_confirm = [];
        foreach (self::NET_KEYS as $net => $short) {
            $val = $this->config->get('payment_algovoi_net_' . $short);
            if ($val === null || $val === '' || $val === '1' || $val === 1) $enabled_confirm[] = $net;
        }
        if (empty($enabled_confirm)) $enabled_confirm = array_keys(self::ALL_NETWORKS);
        if (!in_array($network, $enabled_confirm, true)) $network = $enabled_confirm[0];

        $api_base = rtrim($this->config->get('payment_algovoi_api_base_url') ?: 'https://cloud.algovoi.co.uk', '/');

        $payload = json_encode([
            'amount'             => round((float)$order['total'], 2),
            'currency'           => strtoupper($order['currency_code']),
            'label'              => 'Order #' . $order['order_id'],
            'preferred_network'  => $network,
            'redirect_url'       => $this->url->link('extension/algovoi/payment/algovoi.callback', 'language=' . $this->config->get('config_language'), true),
            'expires_in_seconds' => 3600,
        ]);

        $ch = curl_init($api_base . '/v1/payment-links');
        curl_setopt_array($ch, [
            CURLOPT_POST            => true,
            CURLOPT_POSTFIELDS      => $payload,
            CURLOPT_RETURNTRANSFER  => true,
            CURLOPT_TIMEOUT         => 30,
            CURLOPT_SSL_VERIFYPEER  => true,   // FIX: explicit SSL verification
            CURLOPT_SSL_VERIFYHOST  => 2,
            CURLOPT_HTTPHEADER      => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $api_key,
                'X-Tenant-Id: ' . $tenant_id,
            ],
        ]);
        $response  = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $body = json_decode($response, true);

        if (($http_code === 200 || $http_code === 201) && !empty($body['checkout_url'])) {
            // SSRF guard: checkout URL must be on the same host as api_base
            $checkout_url  = $body['checkout_url'];
            $api_host      = parse_url($api_base, PHP_URL_HOST);
            $checkout_host = parse_url($checkout_url, PHP_URL_HOST);
            if ($api_host && $checkout_host !== $api_host) {
                $json['error'] = $this->language->get('error_payment_failed');
                $this->response->addHeader('Content-Type: application/json');
                $this->response->setOutput(json_encode($json));
                return;
            }
            // Stash token in session so callback() can verify payment on return
            preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $checkout_url, $tm);
            $this->session->data['algovoi_token']    = isset($tm[1]) ? $tm[1] : ($body['id'] ?? '');
            $this->session->data['algovoi_order_id'] = $this->session->data['order_id'];
            $pending_status = (int)$this->config->get('payment_algovoi_pending_status_id') ?: 1;
            $this->model_checkout_order->addHistory($this->session->data['order_id'], $pending_status, 'Awaiting AlgoVoi payment', false);
            $json['redirect'] = $checkout_url;
        } else {
            $json['error'] = $this->language->get('error_payment_failed');
        }

        $this->response->addHeader('Content-Type: application/json');
        $this->response->setOutput(json_encode($json));
    }

    public function callback(): void {
        $lang     = $this->config->get('config_language');
        $token    = $this->session->data['algovoi_token'] ?? '';
        $order_id = $this->session->data['algovoi_order_id'] ?? ($this->session->data['order_id'] ?? 0);
        $api_base = rtrim($this->config->get('payment_algovoi_api_base_url') ?: 'https://cloud.algovoi.co.uk', '/');
        $api_key  = $this->config->get('payment_algovoi_admin_api_key');

        $paid = false;
        $tx_id = '';

        if ($token && $order_id && $api_base && strpos($api_base, 'https://') === 0) {
            $ch = curl_init($api_base . '/checkout/' . rawurlencode($token) . '/status');
            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT        => 15,
                CURLOPT_SSL_VERIFYPEER => true,
                CURLOPT_SSL_VERIFYHOST => 2,
                CURLOPT_HTTPHEADER     => ['Authorization: Bearer ' . $api_key],
            ]);
            $resp      = curl_exec($ch);
            $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            if ($http_code === 200) {
                $data  = json_decode($resp, true);
                $status = $data['status'] ?? '';
                if (in_array($status, ['paid', 'completed', 'confirmed'], true)) {
                    $paid  = true;
                    $tx_id = $data['tx_id'] ?? '';
                }
            }
        }

        if ($paid) {
            $this->load->model('checkout/order');
            $order = $this->model_checkout_order->getOrder((int)$order_id);
            if ($order && in_array($order['order_status_id'], [1, 2])) {
                $complete_status = (int)$this->config->get('payment_algovoi_complete_status_id') ?: 5;
                $this->model_checkout_order->addHistory(
                    (int)$order_id,
                    $complete_status,
                    'AlgoVoi payment confirmed on return. TX: ' . $tx_id,
                    true
                );
            }
            unset($this->session->data['algovoi_token'], $this->session->data['algovoi_order_id']);
            $this->response->redirect($this->url->link('checkout/success', 'language=' . $lang, true));
        } else {
            // Payment was cancelled or not yet confirmed — send back to checkout with a notice
            unset($this->session->data['algovoi_token'], $this->session->data['algovoi_order_id']);
            $this->session->data['error'] = 'Payment was cancelled or not completed. Please try again.';
            $this->response->redirect($this->url->link('checkout/checkout', 'language=' . $lang, true));
        }
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
                'AlgoVoi payment confirmed. TX: ' . ($data['tx_id'] ?? 'n/a'),
                true
            );
        }

        http_response_code(200);
        echo json_encode(['status' => 'ok']);
        exit;
    }
}
