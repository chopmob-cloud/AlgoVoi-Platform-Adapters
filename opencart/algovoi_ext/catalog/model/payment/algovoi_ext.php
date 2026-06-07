<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
namespace Opencart\Catalog\Model\Extension\AlgovoiExt\Payment;

class AlgovoiExt extends \Opencart\System\Engine\Model {

    public function getMethods(array $address = []): array {
        $this->load->language('extension/algovoi_ext/payment/algovoi_ext');

        if ($this->cart->hasSubscription()) {
            return [];
        }

        if ($this->config->get('payment_algovoi_ext_status')) {
            return [
                'code'       => 'algovoi_ext',
                'name'       => $this->language->get('text_title'),
                'option'     => [
                    'algovoi_ext' => [
                        'code' => 'algovoi_ext.algovoi_ext',
                        'name' => $this->language->get('text_title'),
                    ]
                ],
                'sort_order' => $this->config->get('payment_algovoi_ext_sort_order') ?: 2,
            ];
        }

        return [];
    }
}
