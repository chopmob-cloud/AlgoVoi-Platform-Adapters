"""
AlgoVoi Native Python — Usage Examples

Shows how to integrate AlgoVoi payments into any Python web application.
No framework required — but includes Flask and Django snippets.

Requires only: algovoi.py (zero pip dependencies)
"""

from algovoi import AlgoVoi

av = AlgoVoi(
    api_base="https://api1.ilovechicken.co.uk",
    api_key="algv_YOUR_API_KEY",
    tenant_id="YOUR_TENANT_ID",
    webhook_secret="YOUR_WEBHOOK_SECRET",
)


# ── Example 1: Flask ─────────────────────────────────────────────────────

def flask_example():
    """Minimal Flask integration."""
    from flask import Flask, request, redirect, session, jsonify

    app = Flask(__name__)
    app.secret_key = "change-me"

    @app.route("/checkout")
    def checkout():
        amount = 9.99
        return f"""
        <h2>Checkout — ${amount:.2f}</h2>

        <h3>Hosted Checkout</h3>
        <form method="POST" action="/pay-hosted">
            <input type="hidden" name="amount" value="{amount}">
            {AlgoVoi.render_chain_selector('network', 'hosted')}
            <button type="submit">Pay via Hosted Checkout</button>
        </form>

        <h3>Extension Payment</h3>
        <form method="POST" action="/pay-extension">
            <input type="hidden" name="amount" value="{amount}">
            {AlgoVoi.render_chain_selector('network', 'extension')}
            <button type="submit">Pay via Extension</button>
        </form>
        """

    @app.route("/pay-hosted", methods=["POST"])
    def pay_hosted():
        amount = float(request.form.get("amount", 0))
        network = request.form.get("network", "algorand_mainnet")

        result = av.hosted_checkout(
            amount, "USD", f"Order #{id(request)}", network,
            redirect_url="https://yoursite.com/payment-return",
        )
        if not result:
            return "Payment could not be initiated.", 500

        session["algovoi_token"] = result["token"]
        return redirect(result["checkout_url"])

    @app.route("/payment-return")
    def payment_return():
        token = session.pop("algovoi_token", "")

        # CRITICAL: verify before marking as paid
        if token and av.verify_hosted_return(token):
            return "<h1>Payment confirmed!</h1>"
        else:
            return "<h1>Payment not completed</h1><p>Order is pending.</p>"

    @app.route("/pay-extension", methods=["POST"])
    def pay_extension():
        amount = float(request.form.get("amount", 0))
        network = request.form.get("network", "algorand_mainnet")

        payment_data = av.extension_checkout(amount, "USD", f"Order #{id(request)}", network)
        if not payment_data:
            return "Payment could not be initiated.", 500

        session["algovoi_token"] = payment_data["token"]
        return AlgoVoi.render_extension_payment_ui(payment_data, "/verify-extension", "/payment-success")

    @app.route("/verify-extension", methods=["POST"])
    def verify_extension():
        token = session.get("algovoi_token", "")
        data = request.get_json(silent=True) or {}
        tx_id = (data.get("tx_id") or "").strip()

        if not token or not tx_id or len(tx_id) > 200:
            return jsonify(error="Missing tx_id or session expired."), 400

        result = av.verify_extension_payment(token, tx_id)
        if result.get("_http_code") == 200:
            session.pop("algovoi_token", None)
            return jsonify(success=True)
        return jsonify(error=result.get("detail", "Verification failed.")), 422

    @app.route("/webhook", methods=["POST"])
    def webhook():
        payload = av.verify_webhook(
            request.get_data(),
            request.headers.get("X-AlgoVoi-Signature", ""),
        )
        if not payload:
            return "Unauthorized", 401

        # Process webhook — mark order as paid
        order_id = payload.get("order_id")
        tx_id = payload.get("tx_id")
        # ... your logic here ...

        return jsonify(ok=True)

    return app


# ── Example 2: Django view functions ─────────────────────────────────────

def django_example():
    """
    Django integration — add these to your views.py and urls.py.

    # urls.py
    urlpatterns = [
        path('pay-hosted/', views.pay_hosted, name='pay_hosted'),
        path('payment-return/', views.payment_return, name='payment_return'),
        path('webhook/', views.webhook, name='algovoi_webhook'),
    ]
    """
    pass  # See Flask example above — same pattern with Django's request/response


# ── Example 3: Plain WSGI ────────────────────────────────────────────────

def wsgi_example():
    """Minimal WSGI application — no framework at all."""

    def application(environ, start_response):
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")

        if path == "/webhook" and method == "POST":
            content_length = int(environ.get("CONTENT_LENGTH", 0))
            raw_body = environ["wsgi.input"].read(content_length)
            signature = environ.get("HTTP_X_ALGOVOI_SIGNATURE", "")

            payload = av.verify_webhook(raw_body, signature)
            if not payload:
                start_response("401 Unauthorized", [("Content-Type", "text/plain")])
                return [b"Unauthorized"]

            # Process webhook...
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b'{"ok":true}']

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not found"]

    return application


if __name__ == "__main__":
    # Run the Flask example
    app = flask_example()
    app.run(debug=False, port=5000)  # nosec B201
