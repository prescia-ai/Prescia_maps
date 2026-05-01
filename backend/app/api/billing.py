"""
Billing API — Stripe subscription management.

Routes (all require auth except the webhook):
  GET   /billing/status    — current user's subscription status
  POST  /billing/checkout  — create a Stripe Checkout session
  POST  /billing/portal    — create a Stripe Billing Portal session
  POST  /webhooks/stripe   — Stripe webhook (no auth; verifies signature)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.models.database import User, get_db
from app.models.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PortalSessionResponse,
    SubscriptionStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])
webhook_router = APIRouter(tags=["webhooks"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unix_to_dt(ts: Optional[int | float]) -> Optional[datetime]:
    """Convert a Unix timestamp (int/float) to a timezone-aware datetime, or None."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _derive_plan(price_id: Optional[str]) -> Optional[str]:
    """Map a Stripe Price ID to 'monthly' | 'annual' | None."""
    if price_id == settings.STRIPE_PRICE_MONTHLY:
        return "monthly"
    if price_id == settings.STRIPE_PRICE_ANNUAL:
        return "annual"
    return None


async def _sync_subscription(user: User, sub: stripe.Subscription, db: AsyncSession) -> None:
    """
    Idempotently synchronise all subscription fields from a Stripe Subscription object.
    Re-applying the same data is safe because we overwrite with the canonical Stripe values.
    """
    user.subscription_tier = "pro"
    user.subscription_status = sub.status  # trialing, active, past_due, canceled, etc.
    user.subscription_provider = "stripe"
    user.stripe_subscription_id = sub.id

    # Derive plan from first line-item price
    try:
        price_id: Optional[str] = sub["items"]["data"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        price_id = None
    user.subscription_plan = _derive_plan(price_id)

    user.trial_ends_at = _unix_to_dt(sub.get("trial_end"))
    user.current_period_end = _unix_to_dt(sub.get("current_period_end"))

    await db.flush()


# ---------------------------------------------------------------------------
# GET /billing/status
# ---------------------------------------------------------------------------

@router.get(
    "/billing/status",
    response_model=SubscriptionStatusResponse,
    summary="Get current user's subscription status",
)
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
) -> SubscriptionStatusResponse:
    """Return the subscription status for the authenticated user."""
    if current_user.is_admin:
        return SubscriptionStatusResponse(
            tier="pro",
            status="admin",
            plan=None,
            trial_ends_at=None,
            current_period_end=None,
            canceled_at=None,
            is_pro=True,
            has_payment_method=False,
        )

    has_payment_method = False
    if current_user.stripe_customer_id and settings.STRIPE_SECRET_KEY:
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            payment_methods = stripe.PaymentMethod.list(
                customer=current_user.stripe_customer_id,
                type="card",
                limit=1,
            )
            has_payment_method = len(payment_methods.data) > 0
        except stripe.StripeError:
            pass

    return SubscriptionStatusResponse(
        tier=current_user.subscription_tier or "free",
        status=current_user.subscription_status or "none",
        plan=current_user.subscription_plan,
        trial_ends_at=current_user.trial_ends_at,
        current_period_end=current_user.current_period_end,
        canceled_at=current_user.canceled_at,
        is_pro=current_user.is_pro,
        has_payment_method=has_payment_method,
    )


# ---------------------------------------------------------------------------
# POST /billing/checkout
# ---------------------------------------------------------------------------

@router.post(
    "/billing/checkout",
    response_model=CheckoutSessionResponse,
    summary="Create a Stripe Checkout session",
)
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutSessionResponse:
    """
    Create a Stripe Checkout session for the current user.

    - Creates a Stripe customer if one does not already exist.
    - Offers a 7-day free trial on the first ever subscription (detected by
      trial_ends_at and current_period_end both being None).
    - Enables automatic tax collection via Stripe Tax.
    """
    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins do not require a subscription",
        )

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured on this server.",
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Map plan → price ID
    if payload.plan == "monthly":
        price_id = settings.STRIPE_PRICE_MONTHLY
    else:
        price_id = settings.STRIPE_PRICE_ANNUAL

    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe price IDs are not configured.",
        )

    # Ensure the user has a Stripe customer record
    if not current_user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            metadata={"user_id": str(current_user.id)},
        )
        current_user.stripe_customer_id = customer.id
        await db.flush()

    # Only offer a trial on first subscription (never trialed before)
    is_first_subscription = (
        current_user.trial_ends_at is None
        and current_user.current_period_end is None
    )

    session_params: dict = {
        "customer": current_user.stripe_customer_id,
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": payload.success_url,
        "cancel_url": payload.cancel_url,
        "automatic_tax": {"enabled": True},
        "tax_id_collection": {"enabled": True},
        "allow_promotion_codes": True,
        "subscription_data": {
            "metadata": {"user_id": str(current_user.id)},
        },
    }

    if is_first_subscription:
        session_params["subscription_data"]["trial_period_days"] = 7

    session = stripe.checkout.Session.create(**session_params)
    return CheckoutSessionResponse(checkout_url=session.url)


# ---------------------------------------------------------------------------
# POST /billing/portal
# ---------------------------------------------------------------------------

@router.post(
    "/billing/portal",
    response_model=PortalSessionResponse,
    summary="Create a Stripe Billing Portal session",
)
async def create_portal_session(
    current_user: User = Depends(get_current_user),
) -> PortalSessionResponse:
    """
    Create a Stripe Billing Portal session for the current user.

    Returns 400 if the user has no Stripe customer ID (never subscribed).
    """
    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins do not require a subscription",
        )

    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Please subscribe first.",
        )

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured on this server.",
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY
    portal_session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
    )
    return PortalSessionResponse(portal_url=portal_session.url)


# ---------------------------------------------------------------------------
# POST /webhooks/stripe  (no auth — signature verified)
# ---------------------------------------------------------------------------

@webhook_router.post(
    "/webhooks/stripe",
    summary="Stripe webhook endpoint",
    status_code=status.HTTP_200_OK,
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive and process Stripe webhook events.

    Verifies the Stripe-Signature header; rejects with 400 on failure.
    Handles:
      - customer.subscription.created
      - customer.subscription.updated
      - customer.subscription.deleted
      - customer.subscription.trial_will_end  (log only)
      - invoice.payment_succeeded
      - invoice.payment_failed
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret is not configured.",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature.",
        ) from exc
    except Exception as exc:
        logger.error("Error parsing Stripe webhook payload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        ) from exc

    event_type: str = event["type"]
    logger.info("Stripe webhook received: %s (id=%s)", event_type, event["id"])

    # ── Subscription events ──────────────────────────────────────────────────

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        sub: stripe.Subscription = event["data"]["object"]
        user = await _get_user_by_subscription(sub, db)
        if user:
            await _sync_subscription(user, sub, db)
            logger.info(
                "Synced subscription for user %s: status=%s plan=%s",
                user.id,
                sub.status,
                user.subscription_plan,
            )

    elif event_type == "customer.subscription.deleted":
        sub = event["data"]["object"]
        user = await _get_user_by_subscription(sub, db)
        if user:
            user.subscription_status = "canceled"
            user.canceled_at = datetime.now(timezone.utc)
            await db.flush()
            logger.info("Subscription canceled for user %s", user.id)

    elif event_type == "customer.subscription.trial_will_end":
        sub = event["data"]["object"]
        logger.info(
            "Trial ending soon for customer %s (sub %s). "
            "TODO: send notification in follow-up PR.",
            sub.get("customer"),
            sub.get("id"),
        )

    # ── Invoice events ───────────────────────────────────────────────────────

    elif event_type == "invoice.payment_succeeded":
        invoice: stripe.Invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        sub_id = invoice.get("subscription")
        user = await _get_user_by_customer_id(str(customer_id), db) if customer_id else None
        if user:
            user.subscription_status = "active"
            if sub_id:
                try:
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    sub = stripe.Subscription.retrieve(str(sub_id))
                    user.current_period_end = _unix_to_dt(sub.get("current_period_end"))
                except stripe.StripeError as exc:
                    logger.warning("Could not refresh period_end after payment: %s", exc)
            await db.flush()
            logger.info("Payment succeeded for user %s; status=active", user.id)

    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        user = await _get_user_by_customer_id(str(customer_id), db) if customer_id else None
        if user:
            user.subscription_status = "past_due"
            await db.flush()
            logger.info("Payment failed for user %s; status=past_due", user.id)

    return {"received": True}


# ---------------------------------------------------------------------------
# Internal helpers for webhook user lookups
# ---------------------------------------------------------------------------

async def _get_user_by_customer_id(
    customer_id: str, db: AsyncSession
) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    return result.scalar_one_or_none()


async def _get_user_by_subscription(
    sub: stripe.Subscription, db: AsyncSession
) -> Optional[User]:
    """
    Look up the user matching a Stripe Subscription.

    Primary key: stripe_customer_id.
    Fallback: subscription.metadata.user_id (useful before the customer is linked).
    """
    customer_id = sub.get("customer")
    if customer_id:
        user = await _get_user_by_customer_id(str(customer_id), db)
        if user:
            return user

    # Fallback to metadata user_id
    user_id = (sub.get("metadata") or {}).get("user_id")
    if user_id:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    logger.warning(
        "Could not resolve user for subscription %s (customer=%s)",
        sub.get("id"),
        customer_id,
    )
    return None
