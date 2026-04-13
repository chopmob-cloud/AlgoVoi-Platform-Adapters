<?php
/**
 * AlgoVoi Native PHP — Usage Example
 *
 * This shows how to integrate AlgoVoi payments into any PHP application.
 * No framework required — just this file and algovoi.php.
 */

require_once __DIR__ . '/algovoi.php';

$av = new AlgoVoi([
    'api_base'       => 'https://api1.ilovechicken.co.uk',
    'api_key'        => 'algv_YOUR_API_KEY',
    'tenant_id'      => 'YOUR_TENANT_ID',
    'webhook_secret' => 'YOUR_WEBHOOK_SECRET',
]);

// ── Route: checkout page ──────────────────────────────────────────────────

if ($_SERVER['REQUEST_URI'] === '/checkout' && $_SERVER['REQUEST_METHOD'] === 'GET') {
    $amount = 9.99; // Your order total
    ?>
    <!DOCTYPE html>
    <html><head><title>Checkout</title></head>
    <body style="background:#0f1117;color:#e2e8f0;font-family:system-ui;max-width:600px;margin:2rem auto;padding:1rem;">
        <h2>Checkout — $<?= number_format($amount, 2) ?></h2>

        <h3>Option 1: Hosted Checkout</h3>
        <form method="POST" action="/pay-hosted">
            <input type="hidden" name="amount" value="<?= $amount ?>">
            <?= AlgoVoi::renderChainSelector('network', 'hosted') ?>
            <button type="submit" style="margin-top:1rem;padding:.8rem 2rem;background:#3b82f6;color:#fff;border:none;border-radius:8px;cursor:pointer;">
                Pay via Hosted Checkout
            </button>
        </form>

        <hr style="border-color:#2a2d3a;margin:2rem 0;">

        <h3>Option 2: Extension Payment</h3>
        <form method="POST" action="/pay-extension">
            <input type="hidden" name="amount" value="<?= $amount ?>">
            <?= AlgoVoi::renderChainSelector('network', 'extension') ?>
            <button type="submit" style="margin-top:1rem;padding:.8rem 2rem;background:#8b5cf6;color:#fff;border:none;border-radius:8px;cursor:pointer;">
                Pay via Extension
            </button>
        </form>
    </body></html>
    <?php
    exit;
}

// ── Route: hosted checkout redirect ───────────────────────────────────────

if ($_SERVER['REQUEST_URI'] === '/pay-hosted' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $amount  = (float)($_POST['amount'] ?? 0);
    $network = $_POST['network'] ?? 'algorand_mainnet';

    $result = $av->hostedCheckout($amount, 'USD', 'Order #' . time(), $network, 'https://yoursite.com/payment-return');

    if (!$result) {
        http_response_code(500);
        echo 'Payment could not be initiated.';
        exit;
    }

    // Store token in session for verification on return
    session_start();
    $_SESSION['algovoi_token'] = $result['token'];

    // Redirect to hosted checkout
    header('Location: ' . $result['checkout_url']);
    exit;
}

// ── Route: hosted checkout return ─────────────────────────────────────────

if ($_SERVER['REQUEST_URI'] === '/payment-return') {
    session_start();
    $token = $_SESSION['algovoi_token'] ?? '';
    unset($_SESSION['algovoi_token']);

    // CRITICAL: verify payment was actually completed before marking order as paid
    if ($token && $av->verifyHostedReturn($token)) {
        echo '<h1>Payment confirmed!</h1>';
        // Mark your order as paid here
    } else {
        echo '<h1>Payment not completed</h1><p>Your order is pending. If you paid, it will be confirmed shortly via webhook.</p>';
    }
    exit;
}

// ── Route: extension payment page ─────────────────────────────────────────

if ($_SERVER['REQUEST_URI'] === '/pay-extension' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $amount  = (float)($_POST['amount'] ?? 0);
    $network = $_POST['network'] ?? 'algorand_mainnet';

    $paymentData = $av->extensionCheckout($amount, 'USD', 'Order #' . time(), $network);

    if (!$paymentData) {
        http_response_code(500);
        echo 'Payment could not be initiated.';
        exit;
    }

    // Store token in session
    session_start();
    $_SESSION['algovoi_token'] = $paymentData['token'];

    echo '<!DOCTYPE html><html><head><title>Pay with AlgoVoi</title></head>';
    echo '<body style="background:#0f1117;color:#e2e8f0;font-family:system-ui;">';
    echo AlgoVoi::renderExtensionPaymentUI($paymentData, '/verify-extension', '/payment-success');
    echo '</body></html>';
    exit;
}

// ── Route: extension verify endpoint (called by JS) ───────────────────────

if ($_SERVER['REQUEST_URI'] === '/verify-extension' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    session_start();
    $token = $_SESSION['algovoi_token'] ?? '';
    $input = json_decode(file_get_contents('php://input'), true);
    $txId  = trim($input['tx_id'] ?? '');

    if (!$token || !$txId || strlen($txId) > 200) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing tx_id or session expired.']);
        exit;
    }

    $result = $av->verifyExtensionPayment($token, $txId);

    if (($result['_http_code'] ?? 0) === 200) {
        unset($_SESSION['algovoi_token']);
        // Mark your order as paid here
        echo json_encode(['success' => true]);
    } else {
        http_response_code($result['_http_code'] ?? 422);
        echo json_encode(['error' => $result['detail'] ?? 'Verification failed.']);
    }
    exit;
}

// ── Route: webhook receiver ───────────────────────────────────────────────

if ($_SERVER['REQUEST_URI'] === '/webhook' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $rawBody  = file_get_contents('php://input');
    $signature = $_SERVER['HTTP_X_ALGOVOI_SIGNATURE'] ?? '';

    $payload = $av->verifyWebhook($rawBody, $signature);

    if (!$payload) {
        http_response_code(401);
        echo 'Unauthorized';
        exit;
    }

    // Process the webhook — mark order as paid
    $orderId = $payload['order_id'] ?? null;
    $txId    = $payload['tx_id'] ?? null;

    // Your order completion logic here...

    echo json_encode(['ok' => true]);
    exit;
}
