# Billing Setup — Stripe Integration

This guide walks you through setting up Stripe for Prescia's Free + Pro subscription tiers.

---

## 1. Create a Stripe account and enable Stripe Tax

1. Create a free account at [stripe.com](https://stripe.com).
2. In the Stripe Dashboard go to **Settings → Tax** and enable **Stripe Tax**.
3. Register the tax jurisdictions where you have tax obligations (typically the US states where you have nexus, or your country). Stripe will then automatically collect and remit tax for you.

---

## 2. Create the Pro products and prices

1. In the Stripe Dashboard go to **Products → Add product**.
2. Create the first product:
   - **Name:** Prescia Pro Monthly
   - **Pricing model:** Standard pricing
   - **Price:** $4.99 USD, Recurring, Monthly
   - Copy the generated **Price ID** (starts with `price_…`) — you'll use it as `STRIPE_PRICE_MONTHLY`.
3. Create the second product:
   - **Name:** Prescia Pro Annual
   - **Pricing model:** Standard pricing
   - **Price:** $49.99 USD, Recurring, Yearly
   - Copy the **Price ID** — you'll use it as `STRIPE_PRICE_ANNUAL`.

---

## 3. Configure the Customer Portal

1. In the Dashboard go to **Settings → Customer portal**.
2. Enable the following features:
   - ✅ Cancel subscription
   - ✅ Update payment method
   - ✅ Switch plans (monthly ↔ annual)
   - ✅ Update billing address / tax ID
3. Under **Cancellation**, choose **Cancel at end of billing period** — this ensures `is_pro` stays `True` until `current_period_end` and customers don't lose access immediately.
4. Save the configuration.

---

## 4. Set up the webhook endpoint

1. In the Dashboard go to **Developers → Webhooks → Add endpoint**.
2. Enter your backend URL:
   ```
   https://<your-backend-domain>/api/v1/webhooks/stripe
   ```
3. Select the following events to listen for:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `customer.subscription.trial_will_end`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. After saving, click **Reveal** on the **Signing secret** and copy it — this is your `STRIPE_WEBHOOK_SECRET`.

---

## 5. Environment variables

Add the following to your `.env` file (backend) and set them in production:

```env
# Stripe API keys (from Developers → API keys in the Dashboard)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# Webhook signing secret (from step 4 above)
STRIPE_WEBHOOK_SECRET=whsec_...

# Price IDs (from step 2 above)
STRIPE_PRICE_MONTHLY=price_...
STRIPE_PRICE_ANNUAL=price_...
```

For the frontend, add to your `.env`:

```env
# Plumbed for future Apple Pay / embedded payment elements
VITE_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

> **Security note:** Never commit real API keys to source control. Use `.env` files locally and environment secrets in CI/production.

---

## 6. Local development — forwarding webhooks

Stripe cannot reach `localhost` directly. Use the Stripe CLI to forward events:

```bash
# Install the CLI: https://stripe.com/docs/stripe-cli
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

The CLI prints a webhook signing secret (starts with `whsec_`). Use that as `STRIPE_WEBHOOK_SECRET` in your local `.env` while developing.

---

## 7. Test cards

Use these card numbers in Stripe's test mode (any future expiry date, any CVC):

| Card number              | Behaviour                                                                  |
| ------------------------ | -------------------------------------------------------------------------- |
| `4242 4242 4242 4242`    | Always succeeds                                                            |
| `4000 0000 0000 0341`    | Succeeds for trial, fails on first real charge — useful for testing `past_due` |
| `4000 0000 0000 9995`    | Declined (insufficient funds)                                              |

---

## 8. Going live

1. Complete Stripe's account activation (business details, bank account).
2. Switch API keys from test (`sk_test_…` / `pk_test_…`) to live (`sk_live_…` / `pk_live_…`).
3. Create a **live** webhook endpoint (separate from test).
4. Update all environment variables in production with the live values.
