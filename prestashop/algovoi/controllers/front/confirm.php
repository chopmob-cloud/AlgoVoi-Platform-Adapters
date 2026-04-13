<?php
class AlgovoiConfirmModuleFrontController extends ModuleFrontController
{
    public function initContent()
    {
        parent::initContent();
        $order_id = (int)($this->context->cookie->algovoi_order_id ?? 0);
        $token    = (string)($this->context->cookie->algovoi_hosted_token ?? '');

        // Clean up cookies
        $this->context->cookie->__unset('algovoi_order_id');
        $this->context->cookie->__unset('algovoi_hosted_token');
        $this->context->cookie->write();

        if ($order_id && $token) {
            $order = new Order($order_id);

            if (Validate::isLoadedObject($order)) {
                // Verify payment status with AlgoVoi API before marking complete
                $api_base = rtrim(Configuration::get('ALGOVOI_API_BASE_URL'), '/');
                $ch = curl_init($api_base . '/checkout/' . rawurlencode($token));
                curl_setopt_array($ch, [
                    CURLOPT_RETURNTRANSFER => true,
                    CURLOPT_TIMEOUT        => 15,
                    CURLOPT_SSL_VERIFYPEER => true,
                    CURLOPT_SSL_VERIFYHOST => 2,
                ]);
                $response = curl_exec($ch);
                $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
                curl_close($ch);

                $paid = false;
                if ($httpCode === 200) {
                    $data = json_decode($response, true) ?? [];
                    $status = $data['status'] ?? '';
                    if (in_array($status, ['paid', 'completed', 'confirmed'], true)) {
                        $paid = true;
                    }
                }

                if ($paid) {
                    $order->setCurrentState((int)Configuration::get('ALGOVOI_COMPLETE_STATUS') ?: 5);
                }
                // If not paid, order stays in pending — webhook will handle later if payment completes
            }
        }

        Tools::redirect($this->context->link->getPageLink('order-confirmation', true, null, [
            'id_cart'   => $this->context->cart->id ?? 0,
            'id_module' => $this->module->id,
            'key'       => $this->context->customer->secure_key,
        ]));
    }
}
