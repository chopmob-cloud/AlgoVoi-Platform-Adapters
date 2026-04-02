<?php
class Algovoi_ExtPendingModuleFrontController extends ModuleFrontController
{
    public function postProcess()
    {
        // Called via AJAX from the pending.tpl page after the wallet signs and submits the txn.
        // Expects JSON body: { "txid": "...", "cart_id": N }
        $raw   = file_get_contents("php://input");
        $data  = json_decode($raw, true);
        $txid  = isset($data["txid"]) ? preg_replace("/[^A-Z2-7]/", "", strtoupper($data["txid"])) : "";
        $cart_id = (int)($data["cart_id"] ?? 0);

        if (!$txid || !$cart_id) {
            http_response_code(400);
            echo json_encode(["status" => "error", "message" => "Missing txid or cart_id"]);
            exit;
        }

        $cart = new Cart($cart_id);
        if (!Validate::isLoadedObject($cart) || $cart->id_customer != $this->context->customer->id) {
            http_response_code(403);
            echo json_encode(["status" => "error", "message" => "Invalid cart"]);
            exit;
        }

        $total    = (float)$cart->getOrderTotal(true, Cart::BOTH);
        $currency = new Currency($cart->id_currency);

        // Validate order and set to pending status
        $this->module->validateOrder(
            $cart_id,
            (int)Configuration::get("ALGOVOI_EXT_PENDING_STATUS"),
            $total,
            $this->module->displayName,
            "AlgoVoi txid: " . $txid,
            ["transaction_id" => $txid],
            (int)$cart->id_currency,
            false,
            $this->context->customer->secure_key
        );

        $order_id = Order::getIdByCartId($cart_id);
        http_response_code(200);
        echo json_encode([
            "status"   => "pending",
            "order_id" => $order_id,
            "redirect" => $this->context->link->getPageLink("order-confirmation", true, null, [
                "id_cart"   => $cart_id,
                "id_module" => $this->module->id,
                "key"       => $this->context->customer->secure_key,
            ]),
        ]);
        exit;
    }
}
