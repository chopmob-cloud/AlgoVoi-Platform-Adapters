<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
namespace Opencart\Admin\Controller\Extension\Algovoi\Payment;

class Algovoi extends \Opencart\System\Engine\Controller {

    public function index(): void {
        $this->load->language('extension/algovoi/payment/algovoi');
        $this->document->setTitle($this->language->get('heading_title'));

        $data['breadcrumbs'] = [
            ['text' => $this->language->get('text_home'),      'href' => $this->url->link('common/dashboard',      'user_token=' . $this->session->data['user_token'])],
            ['text' => $this->language->get('text_extension'), 'href' => $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=payment')],
            ['text' => $this->language->get('heading_title'),  'href' => $this->url->link('extension/algovoi/payment/algovoi', 'user_token=' . $this->session->data['user_token'])],
        ];

        $data['save'] = $this->url->link('extension/algovoi/payment/algovoi.save', 'user_token=' . $this->session->data['user_token']);
        $data['back'] = $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=payment');

        $fields = ['status','api_base_url','tenant_id','admin_api_key','preferred_network','webhook_secret','sort_order'];
        foreach ($fields as $f) {
            $data['payment_algovoi_' . $f] = $this->config->get('payment_algovoi_' . $f);
        }

        // Pass per-network enabled flags (default on if never saved)
        $nets = ['algorand','voi','hedera','stellar','base','solana','tempo'];
        foreach ($nets as $n) {
            $key = 'payment_algovoi_net_' . $n;
            $val = $this->config->get($key);
            $data[$key] = ($val === null || $val === '' || $val === '1' || $val === 1);
        }

        $this->load->model('localisation/order_status');
        $data['order_statuses'] = $this->model_localisation_order_status->getOrderStatuses();
        $data['payment_algovoi_pending_status_id']   = (int)$this->config->get('payment_algovoi_pending_status_id');
        $data['payment_algovoi_complete_status_id']  = (int)$this->config->get('payment_algovoi_complete_status_id');

        $this->load->model('localisation/geo_zone');
        $data['geo_zones'] = $this->model_localisation_geo_zone->getGeoZones();
        $data['payment_algovoi_geo_zone_id'] = $this->config->get('payment_algovoi_geo_zone_id');

        $data['header']      = $this->load->controller('common/header');
        $data['column_left'] = $this->load->controller('common/column_left');
        $data['footer']      = $this->load->controller('common/footer');

        $this->response->setOutput($this->load->view('extension/algovoi/payment/algovoi', $data));
    }

    public function save(): void {
        $this->load->language('extension/algovoi/payment/algovoi');
        $json = [];

        if (!$this->user->hasPermission('modify', 'extension/algovoi/payment/algovoi')) {
            $json['error']['warning'] = $this->language->get('error_permission');
        }

        if (!$json) {
            $this->load->model('setting/setting');
            $this->model_setting_setting->editSetting('payment_algovoi', $this->request->post);
            $json['success'] = $this->language->get('text_success');
        }

        $this->response->addHeader('Content-Type: application/json');
        $this->response->setOutput(json_encode($json));
    }
}
