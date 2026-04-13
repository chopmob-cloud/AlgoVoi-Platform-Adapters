define([
    'uiComponent',
    'Magento_Checkout/js/model/payment/renderer-list'
], function (Component, rendererList) {
    'use strict';

    rendererList.push({
        type: 'algovoi',
        component: 'Algovoi_Payment/js/view/payment/method-renderer/algovoi'
    });

    return Component.extend({});
});
