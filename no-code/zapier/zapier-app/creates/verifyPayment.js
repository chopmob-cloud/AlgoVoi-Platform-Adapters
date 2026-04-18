'use strict';

const API_BASE = 'https://api1.ilovechicken.co.uk';

const perform = async (z, bundle) => {
  const token = bundle.inputData.token;
  const response = await z.request({
    url: `${API_BASE}/checkout/${encodeURIComponent(token)}/status`,
    method: 'GET',
    throwForStatus: false,
  });

  const data   = response.data || {};
  const status = String(data.status || 'unknown');
  const paid   = ['paid', 'completed', 'confirmed'].includes(status);

  return { token, paid, status };
};

module.exports = {
  key: 'verify_payment',
  noun: 'Payment',

  display: {
    label: 'Verify Payment',
    description:
      'Checks whether an AlgoVoi checkout token has been paid. ' +
      'Returns `paid: true` and the payment status.',
  },

  operation: {
    perform,
    inputFields: [
      {
        key:      'token',
        label:    'Checkout Token',
        type:     'string',
        required: true,
        helpText:
          'The checkout token from a previous **Create Payment Link** step ' +
          '(or from an AlgoVoi webhook payload).',
      },
    ],

    sample: {
      token:  'abc123token',
      paid:   true,
      status: 'paid',
    },

    outputFields: [
      { key: 'token',  label: 'Checkout Token' },
      { key: 'paid',   label: 'Paid?',          type: 'boolean' },
      { key: 'status', label: 'Payment Status' },
    ],
  },
};
