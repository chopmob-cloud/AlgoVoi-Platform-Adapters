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
        $this->version     = "1.2.0";
        $this->author      = "AlgoVoi";
        $this->author_uri  = "https://api1.ilovechicken.co.uk";
        $this->need_instance = 0;
        $this->bootstrap   = true;
        $this->ps_versions_compliancy = ['min' => '8.0.0', 'max' => _PS_VERSION_];
        parent::__construct();
        $this->displayName = $this->l("AlgoVoi Payment Gateway");
        $this->description = $this->l("Accept USDC / aUSDC / USDCe stablecoin payments on Algorand, VOI, Hedera, Stellar, Base, Solana and Tempo via hosted checkout. Instant settlement, no chargebacks, no FX fees.");
    }

    public function install()
    {
        return parent::install()
            && $this->registerHook("paymentOptions")
            && $this->registerHook("paymentReturn")
            && Configuration::updateValue("ALGOVOI_API_BASE_URL",      "https://api1.ilovechicken.co.uk")
            && Configuration::updateValue("ALGOVOI_TENANT_ID",        "YOUR_TENANT_ID")
            && Configuration::updateValue("ALGOVOI_API_KEY",          "YOUR_API_KEY")
            && Configuration::updateValue("ALGOVOI_NETWORK",          "algorand_mainnet")
            && Configuration::updateValue("ALGOVOI_ENABLED_NETWORKS", "algorand_mainnet,voi_mainnet,hedera_mainnet,stellar_mainnet,base_mainnet,solana_mainnet,tempo_mainnet")
            && Configuration::updateValue("ALGOVOI_WEBHOOK_SECRET",   "YOUR_WEBHOOK_SECRET")
            && Configuration::updateValue("ALGOVOI_PENDING_STATUS",   1)
            && Configuration::updateValue("ALGOVOI_COMPLETE_STATUS",  5);
    }

    public function uninstall()
    {
        foreach (["ALGOVOI_API_BASE_URL","ALGOVOI_TENANT_ID","ALGOVOI_API_KEY",
                  "ALGOVOI_NETWORK","ALGOVOI_ENABLED_NETWORKS","ALGOVOI_WEBHOOK_SECRET",
                  "ALGOVOI_PENDING_STATUS","ALGOVOI_COMPLETE_STATUS"] as $k) {
            Configuration::deleteByName($k);
        }
        return parent::uninstall();
    }

    // All 7 supported networks — used throughout admin + checkout
    const ALL_NETWORKS = [
        "algorand_mainnet" => "Algorand — USDC",
        "voi_mainnet"      => "VOI — aUSDC",
        "hedera_mainnet"   => "Hedera — USDC",
        "stellar_mainnet"  => "Stellar — USDC",
        "base_mainnet"     => "Base — USDC",
        "solana_mainnet"   => "Solana — USDC",
        "tempo_mainnet"    => "Tempo — USDCe",
    ];

    protected function getEnabledNetworks(): array
    {
        $raw = Configuration::get("ALGOVOI_ENABLED_NETWORKS") ?: implode(",", array_keys(self::ALL_NETWORKS));
        $list = array_filter(array_map("trim", explode(",", $raw)));
        return !empty($list) ? $list : array_keys(self::ALL_NETWORKS);
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
            // Build enabled_networks from individual checkbox posts
            $enabled = [];
            foreach (array_keys(self::ALL_NETWORKS) as $net) {
                if (Tools::getValue("ALGOVOI_NET_" . strtoupper(str_replace("_", "", $net)))) {
                    $enabled[] = $net;
                }
            }
            Configuration::updateValue("ALGOVOI_ENABLED_NETWORKS", implode(",", $enabled ?: array_keys(self::ALL_NETWORKS)));
            $output .= $this->displayConfirmation($this->l("Settings saved."));
        }
        return $output . $this->renderForm();
    }

    protected function renderForm()
    {
        $enabled = $this->getEnabledNetworks();
        $net_checkboxes = [];
        foreach (self::ALL_NETWORKS as $value => $label) {
            $key = "ALGOVOI_NET_" . strtoupper(str_replace("_", "", $value));
            $net_checkboxes[] = ["id" => $key, "name" => $label, "val" => $value];
        }

        $fields_form = [["form" => [
            "legend" => ["title" => $this->l("AlgoVoi Settings"), "icon" => "icon-cogs"],
            "input"  => [
                ["type"=>"text","label"=>$this->l("API Base URL"),      "name"=>"ALGOVOI_API_BASE_URL",   "required"=>true],
                ["type"=>"text","label"=>$this->l("Tenant ID"),         "name"=>"ALGOVOI_TENANT_ID",      "required"=>true],
                ["type"=>"text","label"=>$this->l("API Key"),           "name"=>"ALGOVOI_API_KEY",        "required"=>true],
                ["type"=>"select","label"=>$this->l("Default Network"), "name"=>"ALGOVOI_NETWORK","required"=>true,
                    "options"=>["query"=>array_map(fn($v,$l)=>["id"=>$v,"name"=>$l],
                        array_keys(self::ALL_NETWORKS), array_values(self::ALL_NETWORKS)),
                    "id"=>"id","name"=>"name"]],
                ["type"=>"checkbox","label"=>$this->l("Enabled Networks"),
                    "name"=>"ALGOVOI_NET","desc"=>$this->l("Networks shown at checkout. One selected = selector hidden, used automatically."),
                    "values"=>["query"=>$net_checkboxes,"id"=>"id","name"=>"name"]],
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
        foreach (self::ALL_NETWORKS as $value => $label) {
            $key = "ALGOVOI_NET_" . strtoupper(str_replace("_", "", $value));
            $helper->fields_value[$key] = in_array($value, $enabled);
        }
        return $helper->generateForm($fields_form);
    }

    public function hookPaymentOptions($params)
    {
        if (!$this->active) return;
        $actionUrl = $this->context->link->getModuleLink("algovoi", "payment", [], true);
        $enabled   = $this->getEnabledNetworks();
        $chains    = array_intersect_key(self::ALL_NETWORKS, array_flip($enabled));
        if (empty($chains)) $chains = self::ALL_NETWORKS;

        if (count($chains) === 1) {
            $net = array_key_first($chains);
            $chainSelector = '';
            $inputs = [['type' => 'hidden', 'name' => 'algovoi_network', 'value' => $net]];
        } else {
            $options_html = '';
            foreach ($chains as $value => $label) {
                $options_html .= '<option value="' . htmlspecialchars($value, ENT_QUOTES) . '">'
                    . htmlspecialchars($label, ENT_QUOTES) . '</option>';
            }
            $chainSelector = '
        <div style="margin:.5rem 0 .25rem;">
          <label for="algovoi_network_select"
                 style="display:block;font-size:12px;color:#555;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-bottom:.3rem;">
            Select network
          </label>
          <select id="algovoi_network_select"
                  style="padding:.4rem .6rem;border:1px solid #ccc;border-radius:4px;font-size:13px;min-width:220px;"
                  onchange="document.querySelector(\'input[name=algovoi_network]\').value=this.value;">'
                . $options_html . '
          </select>
        </div>';
            $inputs = [['type' => 'hidden', 'name' => 'algovoi_network', 'value' => array_key_first($chains)]];
        }

        $option = new PaymentOption();
        $option->setCallToActionText($this->l("Pay with AlgoVoi Hosted Checkout"))
               ->setAction($actionUrl)
               ->setAdditionalInformation($chainSelector)
               ->setInputs($inputs);
        return [$option];
    }

    public function hookPaymentReturn($params)
    {
        return $this->fetch("module:algovoi/views/templates/hook/payment_return.tpl");
    }
}
