define([
    'Magento_Checkout/js/view/payment/default',
    'ko',
    'mage/url'
], function (Component, ko, urlBuilder) {
    'use strict';

    return Component.extend({
        defaults: {
            template: 'Algovoi_Payment/payment/algovoi',
            selectedNetwork: ko.observable('algorand_mainnet'),
            redirectAfterPlaceOrder: false  // We handle redirect ourselves
        },

        initialize: function () {
            this._super();
            var config = window.checkoutConfig.payment.algovoi || {};
            if (config.defaultNetwork) {
                this.selectedNetwork(config.defaultNetwork);
            }
            return this;
        },

        getCode: function () {
            return 'algovoi';
        },

        getChains: function () {
            var config = window.checkoutConfig.payment.algovoi || {};
            return config.chains || [];
        },

        getData: function () {
            return {
                method: this.getCode(),
                additional_data: {
                    algovoi_network: this.selectedNetwork()
                }
            };
        },

        selectNetwork: function (chain) {
            this.selectedNetwork(chain.value);
            return true;
        },

        afterPlaceOrder: function () {
            // Magento calls getOrderPlaceRedirectUrl() on the payment method
            // and redirects the customer to the AlgoVoi hosted checkout URL.
            // This is handled by the default redirect mechanism in AbstractMethod.
        }
    });
});
