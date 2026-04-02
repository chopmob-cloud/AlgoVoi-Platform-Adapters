{extends file="page.tpl"}

{block name="page_title"}
  {l s='Complete Your AlgoVoi Payment' mod='algovoi_ext'}
{/block}

{block name="page_content"}
<div class="algovoi-wallet-payment" style="max-width:600px;margin:0 auto;padding:2rem;">
  <h3>{l s='Pay with your Algorand / VOI Wallet' mod='algovoi_ext'}</h3>

  <div id="algovoi-amount-box" style="background:#f5f5f5;border-radius:8px;padding:1rem;margin:1rem 0;text-align:center;">
    <p style="font-size:1.5rem;font-weight:bold;margin:0;">
      {$algovoi_amount|escape:'html':'UTF-8'} {$algovoi_currency|escape:'html':'UTF-8'}
    </p>
    <p style="color:#666;margin:0.25rem 0 0;">{$algovoi_label|escape:'html':'UTF-8'}</p>
  </div>

  <div id="algovoi-status" style="margin:1rem 0;padding:0.75rem;border-radius:6px;background:#e8f4fd;color:#0c5460;display:none;"></div>

  <button id="algovoi-pay-btn" class="btn btn-primary btn-lg" style="width:100%;">
    {l s='Connect Wallet & Pay' mod='algovoi_ext'}
  </button>

  <p style="margin-top:1rem;font-size:0.85rem;color:#888;">
    {l s='Supports Pera Wallet, Defly, and Lute. Requires AlgoVoi wallet extension or WalletConnect.' mod='algovoi_ext'}
  </p>
</div>

{literal}
<script>
(function () {
  var txnB64     = "{/literal}{$algovoi_txn_b64|escape:'html':'UTF-8'}{literal}";
  var paymentId  = "{/literal}{$algovoi_payment_id|escape:'html':'UTF-8'}{literal}";
  var network    = "{/literal}{$algovoi_network|escape:'html':'UTF-8'}{literal}";
  var verifyUrl  = "{/literal}{$algovoi_verify_url|escape:'html':'UTF-8'}{literal}";
  var pendingUrl = "{/literal}{$algovoi_pending_url|escape:'html':'UTF-8'}{literal}";
  var apiBase    = "{/literal}{$algovoi_api_base|escape:'html':'UTF-8'}{literal}";
  var apiKey     = "{/literal}{$algovoi_api_key|escape:'html':'UTF-8'}{literal}";
  var tenant     = "{/literal}{$algovoi_tenant|escape:'html':'UTF-8'}{literal}";

  // Derive cart_id from label embedded in page (Cart #N)
  var cartId     = parseInt("{/literal}{$algovoi_label|escape:'html':'UTF-8'}{literal}".replace(/[^0-9]/g,""), 10) || 0;

  var btn        = document.getElementById("algovoi-pay-btn");
  var statusBox  = document.getElementById("algovoi-status");

  function showStatus(msg, type) {
    statusBox.style.display = "block";
    statusBox.style.background = type === "error" ? "#f8d7da" : type === "success" ? "#d4edda" : "#e8f4fd";
    statusBox.style.color = type === "error" ? "#721c24" : type === "success" ? "#155724" : "#0c5460";
    statusBox.textContent = msg;
  }

  function b64ToUint8(b64) {
    var bin = atob(b64), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }

  function uint8ToB64(arr) {
    var binary = "";
    for (var i = 0; i < arr.length; i++) binary += String.fromCharCode(arr[i]);
    return btoa(binary);
  }

  async function submitSignedTxn(stxnB64) {
    // Submit signed transaction directly to algod via AlgoVoi proxy endpoint
    var resp = await fetch(apiBase + "/v1/algod/submit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + apiKey,
        "X-Tenant-Id": tenant,
      },
      body: JSON.stringify({ stxn_b64: stxnB64, network: network }),
    });
    var data = await resp.json();
    if (!resp.ok || !data.txid) throw new Error(data.message || "Submission failed");
    return data.txid;
  }

  async function pollVerify(txid, attempts) {
    attempts = attempts || 0;
    if (attempts > 20) { showStatus("Confirmation is taking longer than expected. Check your order history.", "warning"); return; }
    showStatus("Waiting for on-chain confirmation... (" + (attempts + 1) + "/20)", "info");
    var resp = await fetch(pendingUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ txid: txid, cart_id: cartId }),
    });
    var data = await resp.json();
    if (data.redirect) {
      showStatus("Payment confirmed! Redirecting...", "success");
      setTimeout(function () { window.location.href = data.redirect; }, 1500);
      return;
    }
    setTimeout(function () { pollVerify(txid, attempts + 1); }, 3000);
  }

  btn.addEventListener("click", async function () {
    btn.disabled = true;
    showStatus("Connecting to wallet...", "info");

    try {
      if (!window.algorand) {
        throw new Error("No Algorand wallet extension detected. Please install Pera, Defly, or Lute.");
      }

      // Use AlgoVoi extension API: signAndSendTransactions
      // txns array format: [{ txn: base64(txn.toByte()) }]
      var result = await window.algorand.signAndSendTransactions({
        txns: [{ txn: txnB64 }],
      });

      // result.stxns[0] is the base64-encoded signed transaction bytes
      var stxnB64 = result.stxns[0];
      showStatus("Transaction signed. Submitting to network...", "info");

      var txid = await submitSignedTxn(stxnB64);
      showStatus("Transaction submitted (txid: " + txid.slice(0, 16) + "...). Confirming...", "info");

      await pollVerify(txid, 0);

    } catch (err) {
      showStatus("Error: " + (err.message || err), "error");
      btn.disabled = false;
    }
  });
})();
</script>
{/literal}
{/block}
