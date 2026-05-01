import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { createCheckoutSession, createPortalSession } from '../api/client';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

// ── Feature list ─────────────────────────────────────────────────────────────

const PRO_FEATURES = [
  'Hunt Planning',
  'Hunt Logging (unlimited)',
  'Pins on the map',
  'Groups + Events',
  'Pin submissions',
  'All map layers (1955 aerials, BLM, PAD-US, all 27 site types)',
  'Score Engine',
  'Collection',
];

// ── Sub-components ────────────────────────────────────────────────────────────

function PlanCard({
  plan,
  price,
  period,
  badge,
  onSelect,
  loading,
}: {
  plan: 'monthly' | 'annual';
  price: string;
  period: string;
  badge?: string;
  onSelect: (plan: 'monthly' | 'annual') => void;
  loading: boolean;
}) {
  return (
    <div className="relative flex flex-col bg-white border border-stone-200 rounded-3xl p-6 shadow-sm flex-1">
      {badge && (
        <span className="absolute top-4 right-4 bg-amber-100 text-amber-700 text-xs font-semibold px-2.5 py-1 rounded-full">
          {badge}
        </span>
      )}
      <div className="mb-4">
        <p className="text-sm font-semibold text-stone-500 uppercase tracking-wide mb-1">
          {plan === 'monthly' ? 'Monthly' : 'Annual'}
        </p>
        <p className="text-3xl font-bold text-stone-900">
          {price}
          <span className="text-base font-normal text-stone-400">/{period}</span>
        </p>
        <p className="text-xs text-stone-400 mt-1">7-day free trial</p>
      </div>
      <button
        onClick={() => onSelect(plan)}
        disabled={loading}
        className="mt-auto w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-2xl transition-colors text-sm flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Redirecting…
          </>
        ) : (
          'Start 7-day Free Trial'
        )}
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SubscriptionSettingsPage() {
  const { user, subscription, isPro, loading: authLoading, refreshSubscription } = useAuth();
  const navigate = useNavigate();

  const [checkoutLoading, setCheckoutLoading] = useState<'monthly' | 'annual' | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Checkout return handling
  const [successBanner, setSuccessBanner] = useState(false);
  const [cancelBanner, setCancelBanner] = useState(false);
  const [processingBanner, setProcessingBanner] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Redirect if not logged in
  useEffect(() => {
    if (!authLoading && user === null) {
      navigate('/login', { replace: true });
    }
  }, [authLoading, user, navigate]);

  // Handle ?checkout=success|cancel query params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const checkoutParam = params.get('checkout');

    if (checkoutParam === 'success') {
      setSuccessBanner(true);
      refreshSubscription();

      // Poll for up to ~5 sec for the webhook to process
      let attempts = 0;
      const poll = () => {
        attempts += 1;
        refreshSubscription().then(() => {
          if (!isPro && attempts < 5) {
            pollingRef.current = setTimeout(poll, 1000);
          } else if (!isPro) {
            setProcessingBanner(true);
          }
        });
      };
      pollingRef.current = setTimeout(poll, 1000);
    } else if (checkoutParam === 'cancel') {
      setCancelBanner(true);
      setTimeout(() => setCancelBanner(false), 6000);
    }

    if (checkoutParam) {
      window.history.replaceState({}, '', window.location.pathname);
    }

    return () => {
      if (pollingRef.current) clearTimeout(pollingRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCheckout(plan: 'monthly' | 'annual') {
    setCheckoutLoading(plan);
    setError(null);
    try {
      const { checkout_url } = await createCheckoutSession(plan);
      window.location.href = checkout_url;
    } catch {
      setError('Could not start checkout. Please try again.');
      setCheckoutLoading(null);
    }
  }

  async function handlePortal() {
    setPortalLoading(true);
    setError(null);
    try {
      const { portal_url } = await createPortalSession();
      window.location.href = portal_url;
    } catch {
      setError('Could not open billing portal. Please try again.');
    } finally {
      setPortalLoading(false);
    }
  }

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="w-6 h-6 border-2 border-stone-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const status = subscription?.status ?? 'none';
  const tier = subscription?.tier ?? 'free';
  const plan = subscription?.plan;
  const trialEndsAt = subscription?.trial_ends_at;
  const currentPeriodEnd = subscription?.current_period_end;

  // "canceled but expired" = tier is free OR (canceled and past period end)
  const isCanceledExpired =
    status === 'canceled' &&
    currentPeriodEnd !== null &&
    currentPeriodEnd !== undefined &&
    new Date(currentPeriodEnd) <= new Date();

  const showFreeView =
    tier === 'free' || status === 'none' || isCanceledExpired;

  const planLabel = plan === 'annual' ? 'Annual Plan' : plan === 'monthly' ? 'Monthly Plan' : 'Pro';

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link
          to="/profile/settings"
          className="text-stone-400 hover:text-stone-600 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <h1 className="text-xl font-semibold text-stone-900">Subscription</h1>
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="mb-4 px-4 py-3 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* ── Checkout success banner ── */}
      {successBanner && (
        <div className="mb-4 px-4 py-3 rounded-2xl bg-green-50 border border-green-200 text-green-700 text-sm flex items-center gap-2">
          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          You're subscribed to Prescia Pro! Welcome 🎉
        </div>
      )}

      {/* ── Processing banner ── */}
      {processingBanner && (
        <div className="mb-4 px-4 py-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-700 text-sm">
          Your subscription is processing — refresh in a moment to see your Pro status.
        </div>
      )}

      {/* ── Cancel banner ── */}
      {cancelBanner && (
        <div className="mb-4 px-4 py-3 rounded-2xl bg-stone-50 border border-stone-200 text-stone-600 text-sm">
          No worries — you can subscribe any time you're ready.
        </div>
      )}

      {/* ── FREE / EXPIRED CANCELED — pitch view ── */}
      {showFreeView && (
        <div className="space-y-6">
          <div className="text-center py-4">
            <h2 className="text-2xl font-bold text-stone-900 mb-2">Unlock Prescia Pro</h2>
            <p className="text-stone-500 text-sm">
              Get access to all features with a 7-day free trial. Cancel anytime.
            </p>
          </div>

          {/* Plan cards */}
          <div className="flex flex-col sm:flex-row gap-4">
            <PlanCard
              plan="monthly"
              price="$4.99"
              period="mo"
              onSelect={handleCheckout}
              loading={checkoutLoading === 'monthly'}
            />
            <PlanCard
              plan="annual"
              price="$49.99"
              period="yr"
              badge="Save 17%"
              onSelect={handleCheckout}
              loading={checkoutLoading === 'annual'}
            />
          </div>

          {/* Feature list */}
          <div className="bg-white border border-stone-200 rounded-3xl p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-stone-700 mb-4">Everything in Pro</h3>
            <ul className="space-y-2">
              {PRO_FEATURES.map((feature) => (
                <li key={feature} className="flex items-start gap-2 text-sm text-stone-600">
                  <svg
                    className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  {feature}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* ── TRIALING ── */}
      {status === 'trialing' && !isCanceledExpired && (
        <div className="space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-3xl p-5">
            <p className="text-sm font-semibold text-amber-800">
              🎉 Trial active — ends {formatDate(trialEndsAt)}
            </p>
            <p className="text-xs text-amber-600 mt-1">
              You're on the {planLabel}. Your card will be charged when the trial ends.
            </p>
          </div>
          <button
            onClick={handlePortal}
            disabled={portalLoading}
            className="w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-50 text-white font-medium py-3 rounded-2xl transition-colors text-sm flex items-center justify-center gap-2"
          >
            {portalLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Opening…
              </>
            ) : (
              'Manage Subscription'
            )}
          </button>
        </div>
      )}

      {/* ── ACTIVE ── */}
      {status === 'active' && !isCanceledExpired && (
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 rounded-3xl p-5">
            <p className="text-sm font-semibold text-green-800">
              ✓ Prescia Pro — {planLabel}
            </p>
            <p className="text-xs text-green-600 mt-1">
              Renews on {formatDate(currentPeriodEnd)}
            </p>
          </div>
          <button
            onClick={handlePortal}
            disabled={portalLoading}
            className="w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-50 text-white font-medium py-3 rounded-2xl transition-colors text-sm flex items-center justify-center gap-2"
          >
            {portalLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Opening…
              </>
            ) : (
              'Manage Subscription'
            )}
          </button>
        </div>
      )}

      {/* ── PAST_DUE ── */}
      {status === 'past_due' && !isCanceledExpired && (
        <div className="space-y-4">
          <div className="bg-red-50 border border-red-200 rounded-3xl p-5">
            <p className="text-sm font-semibold text-red-800">
              ⚠️ Payment failed
            </p>
            <p className="text-xs text-red-600 mt-1">
              Your last payment didn't go through. Update your payment method to keep Pro access.
            </p>
          </div>
          <button
            onClick={handlePortal}
            disabled={portalLoading}
            className="w-full bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-medium py-3 rounded-2xl transition-colors text-sm flex items-center justify-center gap-2"
          >
            {portalLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Opening…
              </>
            ) : (
              'Update Payment Method'
            )}
          </button>
        </div>
      )}

      {/* ── CANCELED (still in period) ── */}
      {status === 'canceled' && !isCanceledExpired && (
        <div className="space-y-4">
          <div className="bg-stone-50 border border-stone-200 rounded-3xl p-5">
            <p className="text-sm font-semibold text-stone-700">
              Subscription canceled
            </p>
            <p className="text-xs text-stone-500 mt-1">
              Pro access continues until {formatDate(currentPeriodEnd)}.
            </p>
          </div>
          <button
            onClick={handlePortal}
            disabled={portalLoading}
            className="w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-50 text-white font-medium py-3 rounded-2xl transition-colors text-sm flex items-center justify-center gap-2"
          >
            {portalLoading ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Opening…
              </>
            ) : (
              'Reactivate Subscription'
            )}
          </button>
        </div>
      )}
    </div>
  );
}
