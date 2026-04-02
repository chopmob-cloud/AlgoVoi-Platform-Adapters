<?php
namespace Opencart\Catalog\Model\Extension\Algovoi\Payment;

class Algovoi extends \Opencart\System\Engine\Model {

    public function getMethods(array $address = []): array {
        $this->load->language('extension/algovoi/payment/algovoi');

        if ($this->cart->hasSubscription()) {
            $status = false;
        } elseif (!$this->config->get('payment_algovoi_geo_zone_id')) {
            $status = true;
        } else {
            $this->load->model('localisation/geo_zone');
            $results = $this->model_localisation_geo_zone->getGeoZone(
                (int)$this->config->get('payment_algovoi_geo_zone_id'),
                (int)($address['country_id'] ?? 0),
                (int)($address['zone_id'] ?? 0)
            );
            $status = (bool)$results;
        }

        $method_data = [];

        if ($status) {
            $method_data = [
                'code'       => 'algovoi',
                'name'       => $this->language->get('text_title'),
                'option'     => [
                    'algovoi' => [
                        'code' => 'algovoi.algovoi',
                        'name' => $this->language->get('text_title'),
                    ]
                ],
                'sort_order' => $this->config->get('payment_algovoi_sort_order'),
            ];
        }

        return $method_data;
    }
}
