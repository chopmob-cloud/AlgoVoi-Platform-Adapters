<?php
class Algovoi_ExtWebhookModuleFrontController extends ModuleFrontController
{
    public function postProcess()
    {
        $raw_body   = file_get_contents("php://input");
        $secret     = Configuration::get("ALGOVOI_EXT_WEBHOOK_SECRET");
        $sig_header = $_SERVER["HTTP_X_ALGOVOI_SIGNATURE"] ?? "";

        // Reject if webhook secret is not configured — empty key makes HMAC forgeable
        if (empty($secret)) { http_response_code(500); die("Webhook secret not configured"); }

        $expected   = base64_encode(hash_hmac("sha256", $raw_body, $secret, true));
        if (!hash_equals($expected, $sig_header)) { http_response_code(401); die("Unauthorized"); }

        $data = json_decode($raw_body, true);
        if (!empty($data["label"]) && preg_match("/Cart #(\d+)/", $data["label"], $m)) {
            $order_id = (int)Order::getIdByCartId((int)$m[1]);
            if ($order_id) {
                $order = new Order($order_id);
                if (Validate::isLoadedObject($order) && in_array($order->current_state, [
                    (int)Configuration::get("ALGOVOI_EXT_PENDING_STATUS"), 1, 2,
                ])) {
                    $order->setCurrentState((int)Configuration::get("ALGOVOI_EXT_COMPLETE_STATUS") ?: 5);
                    $order->save();
                }
            }
        }
        http_response_code(200);
        echo json_encode(["status" => "ok"]);
        exit;
    }
}
