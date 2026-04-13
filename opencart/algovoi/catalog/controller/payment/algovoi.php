<?php
namespace Opencart\Catalog\Controller\Extension\Algovoi\Payment;

class Algovoi extends \Opencart\System\Engine\Controller {

    public function index(): string {
        $this->load->language('extension/algovoi/payment/algovoi');
        $data['language'] = $this->config->get('config_language');
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
        $allowed   = ['algorand_mainnet', 'voi_mainnet', 'hedera_mainnet', 'stellar_mainnet'];
        if (!in_array($network, $allowed, true)) $network = 'algorand_mainnet';

        $api_base = rtrim($this->config->get('payment_algovoi_api_base_url'), '/');

        $payload = json_encode([
            'amount'             => round((float)$order['total'], 2),
            'currency'           => strtoupper($order['currency_code']),
            'label'              => 'Order #' . $order['order_id'],
            'preferred_network'  => $network,
            'redirect_url'       => $this->url->link('checkout/success', 'language=' . $this->config->get('config_language'), true),
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
            $pending_status = (int)$this->config->get('payment_algovoi_pending_status_id') ?: 1;
            $this->model_checkout_order->addHistory($this->session->data['order_id'], $pending_status, 'Awaiting AlgoVoi payment', false);
            $json['redirect'] = $checkout_url;
        } else {
            $json['error'] = $this->language->get('error_payment_failed');
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
                'AlgoVoi payment confirmed. TX: ' . ($data['tx_id'] ?? 'n/a'),
                true
            );
        }

        http_response_code(200);
        echo json_encode(['status' => 'ok']);
        exit;
    }
}
