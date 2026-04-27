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
        $this->version     = "1.3.0";
        $this->author      = "AlgoVoi";
        $this->author_uri  = "https://www.algovoi.co.uk";
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

    /** Hex colours for each network dot indicator */
    const NET_COLOURS = [
        'algorand_mainnet' => '#3b82f6',
        'voi_mainnet'      => '#8b5cf6',
        'hedera_mainnet'   => '#10b981',
        'stellar_mainnet'  => '#06b6d4',
        'base_mainnet'     => '#2563eb',
        'solana_mainnet'   => '#9333ea',
        'tempo_mainnet'    => '#f59e0b',
    ];

    public function hookPaymentOptions($params)
    {
        if (!$this->active) return;
        $actionUrl = $this->context->link->getModuleLink("algovoi", "payment", [], true);
        $enabled   = $this->getEnabledNetworks();
        $chains    = array_intersect_key(self::ALL_NETWORKS, array_flip($enabled));
        if (empty($chains)) $chains = self::ALL_NETWORKS;

        $firstNet    = array_key_first($chains);
        $firstColour = self::NET_COLOURS[$firstNet] ?? '#3b82f6';
        $coloursJson = json_encode(self::NET_COLOURS);

        if (count($chains) === 1) {
            $selectorHtml = '
      <div style="margin-bottom:14px;display:flex;align-items:center;gap:.6rem;">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;flex-shrink:0;background:' . $firstColour . ';"></span>
        <span style="font-size:13px;color:#e0e0e0;">' . htmlspecialchars(reset($chains), ENT_QUOTES) . '</span>
      </div>';
            $inputs = [['type' => 'hidden', 'name' => 'algovoi_network', 'value' => $firstNet]];
        } else {
            $options_html = '';
            foreach ($chains as $value => $label) {
                $options_html .= '<option value="' . htmlspecialchars($value, ENT_QUOTES) . '">'
                    . htmlspecialchars($label, ENT_QUOTES) . '</option>';
            }
            $selectorHtml = '
      <div style="margin-bottom:16px;">
        <label for="algovoi_ps_sel"
               style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;
                      letter-spacing:.06em;color:#6b7280;margin-bottom:6px;">Select network</label>
        <div style="display:flex;align-items:center;gap:.6rem;">
          <span id="av-ps-dot" style="display:inline-block;width:10px;height:10px;border-radius:50%;
                                       flex-shrink:0;background:' . $firstColour . ';transition:background .2s;"></span>
          <div style="position:relative;flex:1;">
            <select id="algovoi_ps_sel"
                    style="width:100%;padding:.5rem .75rem;background:#0d0e1a;border:1px solid #2a2d3a;
                           border-radius:7px;color:#f1f2f6;font-size:.88rem;cursor:pointer;
                           appearance:none;-webkit-appearance:none;outline:none;transition:border-color .2s;"
                    onfocus="this.style.borderColor=\'#6366f1\'"
                    onblur="this.style.borderColor=\'#2a2d3a\'"
                    onchange="(function(v){var m=' . $coloursJson . ';document.querySelector(\'input[name=algovoi_network]\').value=v;var d=document.getElementById(\'av-ps-dot\');if(d)d.style.background=m[v]||\'#3b82f6\';})(this.value)">'
                . $options_html . '
            </select>
            <span style="position:absolute;right:.7rem;top:50%;transform:translateY(-50%);
                         color:#6b7280;pointer-events:none;font-size:.75rem;">&#9662;</span>
          </div>
        </div>
      </div>';
            $inputs = [['type' => 'hidden', 'name' => 'algovoi_network', 'value' => $firstNet]];
        }

        $panel = '
<div style="background:#141622;border:1px solid #1f2235;border-radius:10px;
            padding:16px 20px;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;margin-top:8px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="width:26px;height:26px;border-radius:7px;background:linear-gradient(135deg,#6366f1,#8b5cf6);
                   display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;">&#9670;</span>
      <strong style="color:#fff;font-size:14px;font-weight:700;">AlgoVoi</strong>
      <span style="font-size:11px;color:#6b7280;border:1px solid #1f2235;border-radius:4px;padding:2px 7px;">Hosted</span>
    </div>
    <div style="display:flex;gap:6px;">
      <span style="font-size:10px;background:rgba(99,102,241,.1);color:#818cf8;border-radius:4px;padding:2px 7px;font-weight:600;">Secure checkout</span>
      <span style="font-size:10px;background:rgba(245,158,11,.1);color:#fbbf24;border-radius:4px;padding:2px 7px;font-weight:600;">Redirect</span>
    </div>
  </div>
  <p style="margin:0 0 12px;font-size:12px;color:#9ca3af;line-height:1.6;">
    Pay with USDC / aUSDC / USDCe stablecoins via hosted checkout. You will be redirected after confirming your order.
  </p>'
  . $selectorHtml . '
  <div style="padding-top:.6rem;border-top:1px solid #1f2235;
              display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.4rem;">
    <span style="font-size:.7rem;color:#4b5563;">
      Secured by
      <a href="https://www.algovoi.co.uk" target="_blank" rel="noopener"
         style="color:#6366f1;text-decoration:none;font-weight:600;">AlgoVoi</a>
      &mdash; instant on-chain settlement
    </span>
    <span style="font-size:.7rem;color:#374151;">No chargebacks &bull; No FX fees</span>
  </div>
</div>';

        $option = new PaymentOption();
        $option->setCallToActionText($this->l("Pay with AlgoVoi"))
               ->setAction($actionUrl)
               ->setAdditionalInformation($panel)
               ->setInputs($inputs);
        return [$option];
    }

    public function hookPaymentReturn($params)
    {
        return $this->fetch("module:algovoi/views/templates/hook/payment_return.tpl");
    }
}
