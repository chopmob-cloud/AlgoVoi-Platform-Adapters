<?php
class Algovoi_ExtPaymentModuleFrontController extends ModuleFrontController
{
    public function initContent()
    {
        parent::initContent();

        $cart = $this->context->cart;
        if (!$cart->id || $cart->id_customer == 0 || !Validate::isLoadedObject($this->context->customer)) {
            Tools::redirect("index.php?controller=order&step=1");
        }

        $api_base = rtrim(Configuration::get("ALGOVOI_EXT_API_BASE_URL"), "/");
        $api_key  = Configuration::get("ALGOVOI_EXT_API_KEY");
        $tenant   = Configuration::get("ALGOVOI_EXT_TENANT_ID");
        $network  = Configuration::get("ALGOVOI_EXT_NETWORK") ?: "algorand_mainnet";
        $currency = new Currency($cart->id_currency);
        $total    = (float)$cart->getOrderTotal(true, Cart::BOTH);
        $label    = "Cart #" . (int)$cart->id;

        // Create a payment request (unsigned transaction) from the API
        $payload = json_encode([
            "amount"            => round($total, 2),
            "currency"          => $currency->iso_code,
            "label"             => $label,
            "preferred_network" => $network,
            "expires_in_seconds"=> 3600,
        ]);

        $ch = curl_init($api_base . "/v1/payment-requests");
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_HTTPHEADER     => [
                "Content-Type: application/json",
                "Authorization: Bearer " . $api_key,
                "X-Tenant-Id: " . $tenant,
            ],
        ]);
        $response  = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        $body = json_decode($response, true);

        if (($http_code !== 200 && $http_code !== 201) || empty($body["txn_b64"])) {
            $this->errors[] = $this->module->l("Could not create payment request. Please try again.");
            $this->redirectWithNotifications($this->context->link->getPageLink("order", true, null, ["step" => 3]));
            return;
        }

        $this->context->smarty->assign([
            "algovoi_txn_b64"     => $body["txn_b64"],
            "algovoi_payment_id"  => $body["id"] ?? "",
            "algovoi_network"     => $network,
            "algovoi_amount"      => round($total, 2),
            "algovoi_currency"    => $currency->iso_code,
            "algovoi_label"       => $label,
            "algovoi_verify_url"  => $this->context->link->getModuleLink("algovoi_ext", "verify", [], true),
            "algovoi_pending_url" => $this->context->link->getModuleLink("algovoi_ext", "pending", [], true),
            "algovoi_api_base"    => $api_base,
            "algovoi_api_key"     => $api_key,
            "algovoi_tenant"      => $tenant,
        ]);

        $this->setTemplate("module:algovoi_ext/views/templates/front/pending.tpl");
    }
}
