<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
namespace Opencart\Admin\Controller\Extension\AlgovoiExt\Payment;

class AlgovoiExt extends \Opencart\System\Engine\Controller {

    public function index(): void {
        $this->load->language('extension/algovoi_ext/payment/algovoi_ext');
        $this->document->setTitle($this->language->get('heading_title'));
        $this->load->model('setting/setting');

        if ($this->request->server['REQUEST_METHOD'] == 'POST') {
            $this->model_setting_setting->editSetting('payment_algovoi_ext', $this->request->post);
            $this->response->redirect($this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=payment'));
        }

        $data['breadcrumbs'] = [];
        $data['breadcrumbs'][] = ['text' => $this->language->get('text_home'), 'href' => $this->url->link('common/dashboard', 'user_token=' . $this->session->data['user_token'])];
        $data['breadcrumbs'][] = ['text' => $this->language->get('text_extension'), 'href' => $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=payment')];
        $data['breadcrumbs'][] = ['text' => $this->language->get('heading_title'), 'href' => $this->url->link('extension/algovoi_ext/payment/algovoi_ext', 'user_token=' . $this->session->data['user_token'])];

        $data['action'] = $this->url->link('extension/algovoi_ext/payment/algovoi_ext', 'user_token=' . $this->session->data['user_token']);
        $data['cancel'] = $this->url->link('marketplace/extension', 'user_token=' . $this->session->data['user_token'] . '&type=payment');

        $data['payment_algovoi_ext_status']     = $this->config->get('payment_algovoi_ext_status') ?? 1;
        $data['payment_algovoi_ext_sort_order'] = $this->config->get('payment_algovoi_ext_sort_order') ?? 2;

        $data['header']         = $this->load->controller('common/header');
        $data['column_left']    = $this->load->controller('common/column_left');
        $data['footer']         = $this->load->controller('common/footer');

        $this->response->setOutput($this->load->view('extension/algovoi_ext/payment/algovoi_ext', $data));
    }

    public function install(): void {
        $this->load->model('setting/setting');
        $this->model_setting_setting->editSetting('payment_algovoi_ext', [
            'payment_algovoi_ext_status'     => 1,
            'payment_algovoi_ext_sort_order' => 2,
        ]);
    }

    public function uninstall(): void {
        $this->load->model('setting/setting');
        $this->model_setting_setting->deleteSetting('payment_algovoi_ext');
    }
}
