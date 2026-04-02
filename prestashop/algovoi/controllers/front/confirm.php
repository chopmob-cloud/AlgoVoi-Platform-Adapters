<?php
class AlgovoiConfirmModuleFrontController extends ModuleFrontController
{
    public function initContent()
    {
        parent::initContent();
        $order_id = (int)($this->context->cookie->algovoi_order_id ?? 0);
        if ($order_id) {
            $order = new Order($order_id);
            if (Validate::isLoadedObject($order)) {
                $order->setCurrentState((int)Configuration::get("ALGOVOI_COMPLETE_STATUS") ?: 5);
            }
            unset($this->context->cookie->algovoi_order_id);
        }
        Tools::redirect($this->context->link->getPageLink("order-confirmation", true, null, [
            "id_cart"   => $this->context->cart->id,
            "id_module" => $this->module->id,
            "key"       => $this->context->customer->secure_key,
        ]));
    }
}
