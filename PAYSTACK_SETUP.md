# Paystack live checkout setup

CyberLord uses Paystack's **hosted checkout redirect**. The browser does not call Paystack's inline JavaScript SDK, so a Paystack public key is not required for this integration. The secret key stays on the server and must never be placed in HTML, JavaScript, GitHub, or a public environment variable.

## Render environment variables

Set these on the CyberLord web service:

- `PAYSTACK_ENABLED` = `true`
- `PAYSTACK_SECRET_KEY` = your Paystack **LIVE secret key** (`sk_live_...`)

Do not use a test key for live transactions. Do not paste the key into source files or commit it to GitHub. If Paystack has not approved the business or issued live keys, checkout remains unavailable; the code cannot bypass Paystack's KYC or account restrictions.

## Paystack webhook

In the Paystack dashboard, configure the webhook URL as:

`https://YOUR-CYBERLORD-DOMAIN/payment/webhook`

Use the actual public domain connected to the Render service. Paystack signs webhook requests; CyberLord validates the signature and then independently verifies the transaction through Paystack's API before activating a plan.

## What activates a plan

A plan activates only when Paystack's server-side verification confirms all of the following against the pending CyberLord payment record:

- transaction status is `success`;
- transaction reference matches the locally generated reference;
- amount matches the exact plan price in kobo;
- currency is `NGN`;
- customer email matches the account that started checkout;
- order metadata matches the local user and selected plan.

The callback and webhook are safe to receive more than once; an already successful payment is not activated a second time. A receipt, screenshot, browser redirect, or unverified webhook body alone cannot activate a subscription.

## Current plan prices

- Pro: NGN 6,300 for 30 days
- Pro Plus: NGN 12,600 for 30 days
- Tutor Pro: NGN 6,300 for 30 days

Checkout is disabled until the business is approved and the live secret key is correctly configured.
