<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
class AlgovoiPaymentModuleFrontController extends ModuleFrontController
{
    public function postProcess()
    {
        $cart = $this->context->cart;
        if (!$cart->id || $cart->id_customer == 0 || !Validate::isLoadedObject($this->context->customer)) {
            Tools::redirect("index.php?controller=order&step=1");
        }

        $api_base = rtrim(Configuration::get("ALGOVOI_API_BASE_URL"), "/");
        $api_key  = Configuration::get("ALGOVOI_API_KEY");
        $tenant   = Configuration::get("ALGOVOI_TENANT_ID");
        $network  = Tools::getValue("algovoi_network") ?: Configuration::get("ALGOVOI_NETWORK") ?: "algorand_mainnet";
        $allowed  = ["algorand_mainnet", "voi_mainnet", "hedera_mainnet", "stellar_mainnet", "base_mainnet", "solana_mainnet", "tempo_mainnet"];
        if (!in_array($network, $allowed, true)) $network = "algorand_mainnet";
        $currency = new Currency($cart->id_currency);
        $total    = (float)$cart->getOrderTotal(true, Cart::BOTH);

        $payload = json_encode([
            "amount"            => round($total, 2),
            "currency"          => $currency->iso_code,
            "label"             => "Cart #" . (int)$cart->id,
            "preferred_network" => $network,
            "redirect_url"      => $this->context->link->getModuleLink("algovoi", "confirm", [], true),
            "expires_in_seconds"=> 3600,
        ]);

        $ch = curl_init($api_base . "/v1/payment-links");
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
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

        if (($http_code === 200 || $http_code === 201) && !empty($body["checkout_url"])) {
            // Extract token from checkout URL
            $token = '';
            if (preg_match('#/checkout/([A-Za-z0-9_-]+)$#', $body["checkout_url"], $m)) {
                $token = $m[1];
            }

            $this->module->validateOrder(
                (int)$cart->id,
                (int)Configuration::get("ALGOVOI_PENDING_STATUS"),
                $total,
                $this->module->displayName,
                "Awaiting AlgoVoi payment. Token: " . $token,
                ['transaction_id' => $token],
                (int)$cart->id_currency,
                false,
                $this->context->customer->secure_key
            );
            $order_id = Order::getIdByCartId((int)$cart->id);
            $this->context->cookie->__set('algovoi_order_id', (string)$order_id);
            $this->context->cookie->__set('algovoi_hosted_token', $token);
            $this->context->cookie->write();
            Tools::redirect($body["checkout_url"]);
        } else {
            $this->errors[] = $this->module->l("Payment could not be initiated. Please try again.");
            $this->redirectWithNotifications($this->context->link->getPageLink("order", true, null, ["step" => 3]));
        }
    }
}
