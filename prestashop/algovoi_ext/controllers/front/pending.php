<?php
// Deprecated — order creation now handled in payment.php (v2.4.1)
// Retained as empty stub to avoid 404 on stale URLs.
class Algovoi_ExtPendingModuleFrontController extends ModuleFrontController
{
    public function postProcess()
    {
        Tools::redirect($this->context->link->getPageLink('order', true, null, ['step' => 3]));
    }
}
