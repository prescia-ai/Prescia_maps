import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { fetchAdminStats } from '../api/client';

const fmt = new Intl.NumberFormat('en-US');

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white border border-stone-200 rounded-2xl px-5 py-4 shadow-sm">
      <p className="text-xs text-stone-500 mb-1">{label}</p>
      <p className="text-2xl font-semibold text-stone-900">{value}</p>
    </div>
  );
}

function SectionHeading({ title }: { title: string }) {
  return (
    <h2 className="text-sm font-semibold text-stone-500 uppercase tracking-wide mt-6 mb-3">
      {title}
    </h2>
  );
}

export default function AdminStatsPage() {
  const { user, profile, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!authLoading && user === null) {
      navigate('/login', { replace: true });
    }
  }, [authLoading, user, navigate]);

  useEffect(() => {
    if (!authLoading && profile !== null && !profile.is_admin) {
      setTimeout(() => navigate('/map', { replace: true }), 2000);
    }
  }, [authLoading, profile, navigate]);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: fetchAdminStats,
    enabled: !!user,
  });

  if (!authLoading && profile !== null && !profile.is_admin) {
    return (
      <div className="min-h-screen bg-stone-50 text-stone-900 flex items-center justify-center">
        <p className="text-red-600 text-sm">Access denied. Redirecting…</p>
      </div>
    );
  }

  return (
    <div className="text-stone-900">
      {/* Page header */}
      <div className="border-b border-stone-200 bg-white shadow-sm sticky top-14 z-10">
        <div className="max-w-4xl mx-auto flex items-center gap-3 px-4 h-12">
          <span className="text-stone-700 text-sm font-medium">Platform Statistics</span>
          <div className="flex-1" />
          {data && (
            <span className="text-xs text-stone-400">
              Last updated{' '}
              {new Date(data.generated_at).toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          )}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-xs bg-white hover:bg-stone-50 border border-stone-200 text-stone-600 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
          >
            {isFetching ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <span className="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : isError ? (
          <div className="text-center py-16 text-red-500 text-sm">
            Failed to load statistics. You may not have admin access.
          </div>
        ) : data ? (
          <>
            <SectionHeading title="Users" />
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="Total Users" value={fmt.format(data.total_users)} />
              <StatCard label="Admins" value={fmt.format(data.admins)} />
              <StatCard label="Free Users" value={fmt.format(data.free_users)} />
              <StatCard label="Pro Users" value={fmt.format(data.pro_users)} />
            </div>

            <SectionHeading title="Subscriptions" />
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="Trialing" value={fmt.format(data.trialing_users)} />
              <StatCard label="Active" value={fmt.format(data.active_users)} />
              <StatCard label="Past Due" value={fmt.format(data.past_due_users)} />
              <StatCard label="Canceled" value={fmt.format(data.canceled_users)} />
            </div>

            <SectionHeading title="Plans" />
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="Monthly" value={fmt.format(data.plan_monthly)} />
              <StatCard label="Annual" value={fmt.format(data.plan_annual)} />
            </div>

            <SectionHeading title="Growth" />
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="New Users (7d)" value={fmt.format(data.new_users_7d)} />
              <StatCard label="New Users (30d)" value={fmt.format(data.new_users_30d)} />
              <StatCard
                label="Conversion Rate"
                value={`${(data.conversion_rate * 100).toFixed(2)}%`}
              />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
