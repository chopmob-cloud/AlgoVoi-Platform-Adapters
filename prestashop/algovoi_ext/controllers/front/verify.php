<?php
class Algovoi_ExtVerifyModuleFrontController extends ModuleFrontController
{
    public function postProcess()
    {
        // Called by webhook OR by the front-end polling to confirm on-chain settlement.
        // Expects JSON: { "txid": "...", "cart_id": N }
        $raw     = file_get_contents("php://input");
        $data    = json_decode($raw, true);
        $txid    = isset($data["txid"]) ? preg_replace("/[^A-Z2-7]/", "", strtoupper($data["txid"])) : "";
        $cart_id = (int)($data["cart_id"] ?? 0);

        if (!$txid || !$cart_id) {
            http_response_code(400);
            echo json_encode(["status" => "error", "message" => "Missing txid or cart_id"]);
            exit;
        }

        $api_base = rtrim(Configuration::get("ALGOVOI_EXT_API_BASE_URL"), "/");
        $api_key  = Configuration::get("ALGOVOI_EXT_API_KEY");
        $tenant   = Configuration::get("ALGOVOI_EXT_TENANT_ID");

        // Ask AlgoVoi API to verify the transaction
        $ch = curl_init($api_base . "/v1/transactions/" . urlencode($txid) . "/verify");
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 20,
            CURLOPT_HTTPHEADER     => [
                "Authorization: Bearer " . $api_key,
                "X-Tenant-Id: " . $tenant,
            ],
        ]);
        $resp      = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        $result = json_decode($resp, true);

        if ($http_code === 200 && !empty($result["confirmed"])) {
            // Advance order to complete status
            $order_id = (int)Order::getIdByCartId($cart_id);
            if ($order_id) {
                $order = new Order($order_id);
                if (Validate::isLoadedObject($order) && in_array($order->current_state, [
                    (int)Configuration::get("ALGOVOI_EXT_PENDING_STATUS"), 1, 2,
                ])) {
                    $order->setCurrentState((int)Configuration::get("ALGOVOI_EXT_COMPLETE_STATUS") ?: 5);
                    $order->save();
                }
            }
            http_response_code(200);
            echo json_encode(["status" => "confirmed", "order_id" => $order_id]);
        } else {
            http_response_code(202);
            echo json_encode(["status" => "pending"]);
        }
        exit;
    }
}
