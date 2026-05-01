import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import {
  useMyPlans,
  useDeletePlan,
  useDuplicatePlan,
  useUpdatePlanStatus,
} from '../hooks/useHuntPlans';
import { exportPlanGpx, exportPlanPdf } from '../api/client';
import type { HuntPlan, HuntPlanStatus } from '../types';

const STATUS_COLORS: Record<HuntPlanStatus, string> = {
  idea:     'bg-stone-100 text-stone-600',
  planned:  'bg-blue-100 text-blue-700',
  done:     'bg-green-100 text-green-700',
  archived: 'bg-stone-200 text-stone-500',
};

const SITE_TYPE_LABELS: Record<string, string> = {
  dirt:      'Dirt',
  beach:     'Beach',
  water:     'Water',
  park:      'Park',
  yard:      'Yard',
  club_hunt: 'Club Hunt',
};

function PlanCard({
  plan,
  onDelete,
  onDuplicate,
  onArchive,
}: {
  plan: HuntPlan;
  onDelete: (id: string) => void;
  onDuplicate: (id: string) => void;
  onArchive: (id: string, status: HuntPlanStatus) => void;
}) {
  const navigate = useNavigate();
  const dateLabel = plan.planned_date
    ? new Date(plan.planned_date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : null;

  return (
    <div
      className="bg-white border border-stone-200 rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => navigate(`/plans/${plan.id}`)}
    >
      {/* Photo thumbnail */}
      {plan.photo_urls && plan.photo_urls.length > 0 && (
        <div className="h-28 rounded-t-xl overflow-hidden">
          <img
            src={plan.photo_urls[0]}
            alt={plan.title}
            className="w-full h-full object-cover"
          />
        </div>
      )}

      <div className="p-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <h3 className="text-sm font-semibold text-stone-900 leading-tight line-clamp-2">
            {plan.title}
          </h3>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide flex-shrink-0 ${STATUS_COLORS[plan.status]}`}
          >
            {plan.status}
          </span>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-2 text-[11px] text-stone-500 mb-2">
          {plan.site_type && (
            <span className="bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded font-medium">
              {SITE_TYPE_LABELS[plan.site_type] ?? plan.site_type}
            </span>
          )}
          {dateLabel && <span>📅 {dateLabel}</span>}
        </div>

        {/* Notes preview */}
        {plan.notes && (
          <p className="text-xs text-stone-500 line-clamp-2 mb-3">{plan.notes}</p>
        )}

        {/* Quick actions */}
        <div
          className="flex items-center gap-1 border-t border-stone-100 pt-2 mt-2"
          onClick={(e) => e.stopPropagation()}
        >
          <Link
            to={`/plans/${plan.id}/edit`}
            className="flex-1 text-center px-2 py-1 text-[11px] text-stone-600 hover:bg-stone-100 rounded-lg transition-colors"
          >
            Edit
          </Link>
          <button
            onClick={() => onDuplicate(plan.id)}
            className="flex-1 px-2 py-1 text-[11px] text-stone-600 hover:bg-stone-100 rounded-lg transition-colors"
          >
            Copy
          </button>
          <button
            onClick={() =>
              onArchive(plan.id, plan.status === 'archived' ? 'idea' : 'archived')
            }
            className="flex-1 px-2 py-1 text-[11px] text-stone-600 hover:bg-stone-100 rounded-lg transition-colors"
          >
            {plan.status === 'archived' ? 'Unarchive' : 'Archive'}
          </button>
          <button
            onClick={() => {
              if (confirm(`Delete "${plan.title}"? This cannot be undone.`)) {
                onDelete(plan.id);
              }
            }}
            className="flex-1 px-2 py-1 text-[11px] text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            Delete
          </button>
        </div>

        {/* Export */}
        <div
          className="flex items-center gap-1 mt-1"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => exportPlanGpx(plan.id)}
            className="flex-1 px-2 py-1 text-[10px] text-stone-500 hover:bg-stone-100 rounded-lg transition-colors"
          >
            ↓ GPX
          </button>
          <button
            onClick={() => exportPlanPdf(plan.id)}
            className="flex-1 px-2 py-1 text-[10px] text-stone-500 hover:bg-stone-100 rounded-lg transition-colors"
          >
            ↓ PDF
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MyPlansPage() {
  const [q, setQ] = useState('');
  const [sort, setSort] = useState('created_at');
  const [siteType, setSiteType] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showArchived, setShowArchived] = useState(false);

  const { data, isLoading, isError } = useMyPlans({
    q: q || undefined,
    sort,
    order: 'desc',
    site_type: siteType || undefined,
    status: statusFilter || undefined,
    include_archived: showArchived,
  });

  const deleteMutation = useDeletePlan();
  const duplicateMutation = useDuplicatePlan();
  const statusMutation = useUpdatePlanStatus();

  const plans = data?.plans ?? [];
  const total = data?.total ?? 0;

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-stone-900">Hunt Plans</h1>
            {!isLoading && (
              <p className="text-sm text-stone-500 mt-0.5">
                {total} plan{total !== 1 ? 's' : ''}
              </p>
            )}
          </div>
          <Link
            to="/plans/create"
            className="flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Plan a Hunt
          </Link>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 mb-6">
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search plans…"
            className="flex-1 min-w-48 border border-stone-200 rounded-lg px-3 py-1.5 text-sm text-stone-700 placeholder-stone-400 focus:outline-none focus:border-stone-400"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="border border-stone-200 rounded-lg px-3 py-1.5 text-sm text-stone-700 focus:outline-none focus:border-stone-400 bg-white"
          >
            <option value="created_at">Sort: Newest</option>
            <option value="updated_at">Sort: Recently Updated</option>
            <option value="planned_date">Sort: Planned Date</option>
            <option value="title">Sort: Title</option>
          </select>
          <select
            value={siteType}
            onChange={(e) => setSiteType(e.target.value)}
            className="border border-stone-200 rounded-lg px-3 py-1.5 text-sm text-stone-700 focus:outline-none focus:border-stone-400 bg-white"
          >
            <option value="">All Sites</option>
            <option value="dirt">Dirt</option>
            <option value="beach">Beach</option>
            <option value="water">Water</option>
            <option value="park">Park</option>
            <option value="yard">Yard</option>
            <option value="club_hunt">Club Hunt</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-stone-200 rounded-lg px-3 py-1.5 text-sm text-stone-700 focus:outline-none focus:border-stone-400 bg-white"
          >
            <option value="">All Statuses</option>
            <option value="idea">Idea</option>
            <option value="planned">Planned</option>
            <option value="done">Done</option>
            {showArchived && <option value="archived">Archived</option>}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-stone-600 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
              className="rounded border-stone-300"
            />
            Show archived
          </label>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex justify-center py-16">
            <LoadingSpinner message="Loading plans…" />
          </div>
        ) : isError ? (
          <div className="text-center py-16 text-stone-500">
            <p>Failed to load plans. Try again.</p>
          </div>
        ) : plans.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-4xl mb-4">🗺️</div>
            <h2 className="text-lg font-semibold text-stone-700 mb-2">No plans yet</h2>
            <p className="text-stone-500 mb-6 text-sm">
              Plan your next hunt by drawing a zone on the map.
            </p>
            <Link
              to="/plans/create"
              className="inline-flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              Plan a Hunt
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {plans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onDelete={(id) => deleteMutation.mutate(id)}
                onDuplicate={(id) => duplicateMutation.mutate(id)}
                onArchive={(id, newStatus) =>
                  statusMutation.mutate({ planId: id, status: newStatus })
                }
              />
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
