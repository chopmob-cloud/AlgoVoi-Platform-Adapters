<?php
/**
 * AlgoVoi: https://github.com/chopmob-cloud/AlgoVoi-Platform-Adapters
 * Licensed under the Business Source License 1.1 - see LICENSE for details.
 */
if (!defined("_PS_VERSION_")) exit;

use PrestaShop\PrestaShop\Core\Payment\PaymentOption;

class Algovoi extends PaymentModule
{
    public function __construct()
    {
        $this->name        = "algovoi";
        $this->tab         = "payments_gateways";
        $this->version     = "1.0.0";
        $this->author      = "AlgoVoi";
        $this->author_uri  = "https://api1.ilovechicken.co.uk";
        $this->need_instance = 0;
        $this->bootstrap   = true;
        $this->ps_versions_compliancy = ['min' => '8.0.0', 'max' => _PS_VERSION_];
        parent::__construct();
        $this->displayName = $this->l("AlgoVoi Payment Gateway");
        $this->description = $this->l("Accept USDC stablecoin payments on Algorand, VOI, Hedera, and Stellar via hosted checkout. Instant settlement, no chargebacks, no FX fees.");
    }

    public function install()
    {
        return parent::install()
            && $this->registerHook("paymentOptions")
            && $this->registerHook("paymentReturn")
            && Configuration::updateValue("ALGOVOI_API_BASE_URL",   "https://api1.ilovechicken.co.uk")
            && Configuration::updateValue("ALGOVOI_TENANT_ID",      "YOUR_TENANT_ID")
            && Configuration::updateValue("ALGOVOI_API_KEY",        "YOUR_API_KEY")
            && Configuration::updateValue("ALGOVOI_NETWORK",        "algorand_mainnet")
            && Configuration::updateValue("ALGOVOI_WEBHOOK_SECRET", "YOUR_WEBHOOK_SECRET")
            && Configuration::updateValue("ALGOVOI_PENDING_STATUS",  1)
            && Configuration::updateValue("ALGOVOI_COMPLETE_STATUS", 5);
    }

    public function uninstall()
    {
        foreach (["ALGOVOI_API_BASE_URL","ALGOVOI_TENANT_ID","ALGOVOI_API_KEY",
                  "ALGOVOI_NETWORK","ALGOVOI_WEBHOOK_SECRET",
                  "ALGOVOI_PENDING_STATUS","ALGOVOI_COMPLETE_STATUS"] as $k) {
            Configuration::deleteByName($k);
        }
        return parent::uninstall();
    }

    public function getContent()
    {
        $output = "";
        if (Tools::isSubmit("submit_algovoi")) {
            foreach (["ALGOVOI_API_BASE_URL","ALGOVOI_TENANT_ID","ALGOVOI_API_KEY",
                      "ALGOVOI_NETWORK","ALGOVOI_WEBHOOK_SECRET"] as $k) {
                Configuration::updateValue($k, Tools::getValue($k));
            }
            Configuration::updateValue("ALGOVOI_PENDING_STATUS",  (int)Tools::getValue("ALGOVOI_PENDING_STATUS"));
            Configuration::updateValue("ALGOVOI_COMPLETE_STATUS", (int)Tools::getValue("ALGOVOI_COMPLETE_STATUS"));
            $output .= $this->displayConfirmation($this->l("Settings saved."));
        }
        return $output . $this->renderForm();
    }

    protected function renderForm()
    {
        $fields_form = [["form" => [
            "legend" => ["title" => $this->l("AlgoVoi Settings"), "icon" => "icon-cogs"],
            "input"  => [
                ["type"=>"text","label"=>$this->l("API Base URL"),      "name"=>"ALGOVOI_API_BASE_URL",   "required"=>true],
                ["type"=>"text","label"=>$this->l("Tenant ID"),         "name"=>"ALGOVOI_TENANT_ID",      "required"=>true],
                ["type"=>"text","label"=>$this->l("API Key"),           "name"=>"ALGOVOI_API_KEY",        "required"=>true],
                ["type"=>"text","label"=>$this->l("Preferred Network"), "name"=>"ALGOVOI_NETWORK",        "required"=>true],
                ["type"=>"text","label"=>$this->l("Webhook Secret"),    "name"=>"ALGOVOI_WEBHOOK_SECRET", "required"=>false],
                ["type"=>"text","label"=>$this->l("Pending Status ID"), "name"=>"ALGOVOI_PENDING_STATUS", "required"=>true],
                ["type"=>"text","label"=>$this->l("Complete Status ID"),"name"=>"ALGOVOI_COMPLETE_STATUS","required"=>true],
            ],
            "submit" => ["title"=>$this->l("Save"),"class"=>"btn btn-default pull-right"],
        ]]];
        $helper = new HelperForm();
        $helper->module          = $this;
        $helper->name_controller = $this->name;
        $helper->token           = Tools::getAdminTokenLite("AdminModules");
        $helper->currentIndex    = AdminController::$currentIndex . "&configure=" . $this->name;
        $helper->submit_action   = "submit_algovoi";
        $helper->fields_value    = [
            "ALGOVOI_API_BASE_URL"   => Configuration::get("ALGOVOI_API_BASE_URL"),
            "ALGOVOI_TENANT_ID"      => Configuration::get("ALGOVOI_TENANT_ID"),
            "ALGOVOI_API_KEY"        => Configuration::get("ALGOVOI_API_KEY"),
            "ALGOVOI_NETWORK"        => Configuration::get("ALGOVOI_NETWORK"),
            "ALGOVOI_WEBHOOK_SECRET" => Configuration::get("ALGOVOI_WEBHOOK_SECRET"),
            "ALGOVOI_PENDING_STATUS" => Configuration::get("ALGOVOI_PENDING_STATUS"),
            "ALGOVOI_COMPLETE_STATUS"=> Configuration::get("ALGOVOI_COMPLETE_STATUS"),
        ];
        return $helper->generateForm($fields_form);
    }

    public function hookPaymentOptions($params)
    {
        if (!$this->active) return;
        $actionUrl = $this->context->link->getModuleLink("algovoi", "payment", [], true);
        $chainSelector = '
        <div style="margin:.5rem 0 .25rem;font-size:12px;color:#555;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Select network</div>
        <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:.25rem;">
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">
            <input type="radio" name="algovoi_network_radio" value="algorand_mainnet" checked
                   onchange="document.querySelector(\'input[name=algovoi_network]\').value=this.value;"> Algorand &mdash; USDC
          </label>
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">
            <input type="radio" name="algovoi_network_radio" value="voi_mainnet"
                   onchange="document.querySelector(\'input[name=algovoi_network]\').value=this.value;"> VOI &mdash; aUSDC
          </label>
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">
            <input type="radio" name="algovoi_network_radio" value="hedera_mainnet"
                   onchange="document.querySelector(\'input[name=algovoi_network]\').value=this.value;"> Hedera &mdash; USDC
          </label>
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">
            <input type="radio" name="algovoi_network_radio" value="stellar_mainnet"
                   onchange="document.querySelector(\'input[name=algovoi_network]\').value=this.value;"> Stellar &mdash; USDC
          </label>
        </div>';
        $option = new PaymentOption();
        $option->setCallToActionText($this->l("Pay with AlgoVoi Hosted Checkout"))
               ->setAction($actionUrl)
               ->setAdditionalInformation($chainSelector)
               ->setInputs([
                   ['type' => 'hidden', 'name' => 'algovoi_network', 'value' => 'algorand_mainnet'],
               ]);
        return [$option];
    }

    public function hookPaymentReturn($params)
    {
        return $this->fetch("module:algovoi/views/templates/hook/payment_return.tpl");
    }
}
