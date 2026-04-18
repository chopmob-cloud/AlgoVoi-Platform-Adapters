'use strict';

const { version }         = require('./package.json');
const { version: pv }     = require('zapier-platform-core');

const authentication      = require('./authentication');
const paymentConfirmed    = require('./triggers/paymentConfirmed');
const createPaymentLink   = require('./creates/createPaymentLink');
const verifyPayment       = require('./creates/verifyPayment');
const listNetworks        = require('./searches/listNetworks');

const App = {
  version,
  platformVersion: pv,

  authentication,

  beforeRequest: [
    // Attach AlgoVoi auth headers to every outbound request that targets the AlgoVoi API.
    (request, z, bundle) => {
      if (
        request.url &&
        request.url.includes('api1.ilovechicken.co.uk') &&
        !request.headers.Authorization
      ) {
        request.headers.Authorization = `Bearer ${bundle.authData.api_key}`;
        request.headers['X-Tenant-Id'] = bundle.authData.tenant_id;
      }
      return request;
    },
  ],

  afterResponse: [],

  triggers: {
    [paymentConfirmed.key]: paymentConfirmed,
  },

  creates: {
    [createPaymentLink.key]: createPaymentLink,
    [verifyPayment.key]:     verifyPayment,
  },

  searches: {
    [listNetworks.key]: listNetworks,
  },
};

module.exports = App;
