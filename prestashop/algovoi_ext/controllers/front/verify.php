<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
class Algovoi_ExtVerifyModuleFrontController extends ModuleFrontController
{
    public function postProcess()
    {
        $raw   = file_get_contents('php://input');
        $data  = json_decode($raw, true);
        $tx_id = isset($data['tx_id']) ? trim($data['tx_id']) : '';

        $token    = (string)($this->context->cookie->__get('algovoi_token')    ?? '');
        $order_id = (int)($this->context->cookie->__get('algovoi_order_id')    ?? 0);

        // FIX: basic length guard on tx_id
        if (!$tx_id || strlen($tx_id) > 200 || !$token) {
            http_response_code(400);
            echo json_encode(['error' => 'Missing tx_id or session expired.']);
            exit;
        }

        $api_base = rtrim(Configuration::get('ALGOVOI_EXT_API_BASE_URL'), '/');

        // Verify via /checkout/{token}/verify
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
        $result = json_decode($response, true);

        if ($http_code === 200) {
            // Advance order to complete status
            if ($order_id) {
                $order = new Order($order_id);
                if (Validate::isLoadedObject($order)) {
                    // FIX: verify the order belongs to the current customer (prevents cookie-swap attack)
                    if ((int)$this->context->customer->id && (int)$order->id_customer !== (int)$this->context->customer->id) {
                        http_response_code(403);
                        echo json_encode(['error' => 'Unauthorized.']);
                        exit;
                    }
                    $complete = (int)Configuration::get('ALGOVOI_EXT_COMPLETE_STATUS') ?: 5;
                    $order->setCurrentState($complete);
                    $order->save();
                }
            }

            // Clear session tokens
            $this->context->cookie->__unset('algovoi_token');
            $this->context->cookie->__unset('algovoi_order_id');
            $this->context->cookie->write();

            http_response_code(200);
            echo json_encode(['success' => true]);
        } else {
            $detail = $result['detail'] ?? $result['message'] ?? 'Verification failed.';
            if (is_array($detail)) {
                $detail = implode('; ', array_map(function ($e) {
                    return isset($e['msg']) ? $e['msg'] : json_encode($e);
                }, $detail));
            }
            http_response_code(422);
            echo json_encode(['error' => $detail]);
        }
        exit;
    }
}
