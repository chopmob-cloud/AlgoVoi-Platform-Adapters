<?php
if (!defined("_PS_VERSION_")) exit;

use PrestaShop\PrestaShop\Core\Payment\PaymentOption;

class Algovoi_Ext extends PaymentModule
{
    public function __construct()
    {
        $this->name        = "algovoi_ext";
        $this->tab         = "payments_gateways";
        $this->version     = "1.0.0";
        $this->author      = "AlgoVoi";
        $this->need_instance = 0;
        $this->bootstrap   = true;
        parent::__construct();
        $this->displayName = $this->l("AlgoVoi Wallet Checkout");
        $this->description = $this->l("Pay with USDC/aUSDC directly from your Algorand or VOI wallet via browser extension.");
    }

    public function install()
    {
        return parent::install()
            && $this->registerHook("paymentOptions")
            && $this->registerHook("paymentReturn")
            && Configuration::updateValue("ALGOVOI_EXT_API_BASE_URL",   "https://api1.ilovechicken.co.uk")
            && Configuration::updateValue("ALGOVOI_EXT_TENANT_ID",      "YOUR_TENANT_ID")
            && Configuration::updateValue("ALGOVOI_EXT_API_KEY",        "YOUR_API_KEY")
            && Configuration::updateValue("ALGOVOI_EXT_NETWORK",        "algorand_mainnet")
            && Configuration::updateValue("ALGOVOI_EXT_WEBHOOK_SECRET", "YOUR_WEBHOOK_SECRET")
            && Configuration::updateValue("ALGOVOI_EXT_PENDING_STATUS",  1)
            && Configuration::updateValue("ALGOVOI_EXT_COMPLETE_STATUS", 5);
    }

    public function uninstall()
    {
        foreach ([
            "ALGOVOI_EXT_API_BASE_URL", "ALGOVOI_EXT_TENANT_ID", "ALGOVOI_EXT_API_KEY",
            "ALGOVOI_EXT_NETWORK", "ALGOVOI_EXT_WEBHOOK_SECRET",
            "ALGOVOI_EXT_PENDING_STATUS", "ALGOVOI_EXT_COMPLETE_STATUS",
        ] as $k) {
            Configuration::deleteByName($k);
        }
        return parent::uninstall();
    }

    public function getContent()
    {
        $output = "";
        if (Tools::isSubmit("submit_algovoi_ext")) {
            foreach ([
                "ALGOVOI_EXT_API_BASE_URL", "ALGOVOI_EXT_TENANT_ID", "ALGOVOI_EXT_API_KEY",
                "ALGOVOI_EXT_NETWORK", "ALGOVOI_EXT_WEBHOOK_SECRET",
            ] as $k) {
                Configuration::updateValue($k, Tools::getValue($k));
            }
            Configuration::updateValue("ALGOVOI_EXT_PENDING_STATUS",  (int)Tools::getValue("ALGOVOI_EXT_PENDING_STATUS"));
            Configuration::updateValue("ALGOVOI_EXT_COMPLETE_STATUS", (int)Tools::getValue("ALGOVOI_EXT_COMPLETE_STATUS"));
            $output .= $this->displayConfirmation($this->l("Settings saved."));
        }
        return $output . $this->renderForm();
    }

    protected function renderForm()
    {
        $fields_form = [["form" => [
            "legend" => ["title" => $this->l("AlgoVoi Wallet Settings"), "icon" => "icon-cogs"],
            "input"  => [
                ["type"=>"text","label"=>$this->l("API Base URL"),      "name"=>"ALGOVOI_EXT_API_BASE_URL",   "required"=>true],
                ["type"=>"text","label"=>$this->l("Tenant ID"),         "name"=>"ALGOVOI_EXT_TENANT_ID",      "required"=>true],
                ["type"=>"text","label"=>$this->l("API Key"),           "name"=>"ALGOVOI_EXT_API_KEY",        "required"=>true],
                ["type"=>"text","label"=>$this->l("Preferred Network"), "name"=>"ALGOVOI_EXT_NETWORK",        "required"=>true],
                ["type"=>"text","label"=>$this->l("Webhook Secret"),    "name"=>"ALGOVOI_EXT_WEBHOOK_SECRET", "required"=>false],
                ["type"=>"text","label"=>$this->l("Pending Status ID"), "name"=>"ALGOVOI_EXT_PENDING_STATUS", "required"=>true],
                ["type"=>"text","label"=>$this->l("Complete Status ID"),"name"=>"ALGOVOI_EXT_COMPLETE_STATUS","required"=>true],
            ],
            "submit" => ["title"=>$this->l("Save"),"class"=>"btn btn-default pull-right"],
        ]]];
        $helper = new HelperForm();
        $helper->module          = $this;
        $helper->name_controller = $this->name;
        $helper->token           = Tools::getAdminTokenLite("AdminModules");
        $helper->currentIndex    = AdminController::$currentIndex . "&configure=" . $this->name;
        $helper->submit_action   = "submit_algovoi_ext";
        $helper->fields_value    = [
            "ALGOVOI_EXT_API_BASE_URL"   => Configuration::get("ALGOVOI_EXT_API_BASE_URL"),
            "ALGOVOI_EXT_TENANT_ID"      => Configuration::get("ALGOVOI_EXT_TENANT_ID"),
            "ALGOVOI_EXT_API_KEY"        => Configuration::get("ALGOVOI_EXT_API_KEY"),
            "ALGOVOI_EXT_NETWORK"        => Configuration::get("ALGOVOI_EXT_NETWORK"),
            "ALGOVOI_EXT_WEBHOOK_SECRET" => Configuration::get("ALGOVOI_EXT_WEBHOOK_SECRET"),
            "ALGOVOI_EXT_PENDING_STATUS" => Configuration::get("ALGOVOI_EXT_PENDING_STATUS"),
            "ALGOVOI_EXT_COMPLETE_STATUS"=> Configuration::get("ALGOVOI_EXT_COMPLETE_STATUS"),
        ];
        return $helper->generateForm($fields_form);
    }

    public function hookPaymentOptions($params)
    {
        if (!$this->active) return;
        $option = new PaymentOption();
        $option->setCallToActionText($this->l("Pay with AlgoVoi Wallet (USDC / aUSDC)"))
               ->setAction($this->context->link->getModuleLink("algovoi_ext", "payment", [], true))
               ->setAdditionalInformation($this->l("Sign directly with your Pera, Defly, or Lute wallet. No redirect needed."));
        return [$option];
    }

    public function hookPaymentReturn($params)
    {
        return $this->fetch("module:algovoi_ext/views/templates/hook/payment_return.tpl");
    }
}
