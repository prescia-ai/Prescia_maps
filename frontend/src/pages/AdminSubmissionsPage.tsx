import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchAdminSubmissions, exportApprovedSubmissions } from '../api/client';
import type { PinSubmission } from '../types';

type StatusFilter = 'pending' | 'approved' | 'rejected';

function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days !== 1 ? 's' : ''} ago`;
}

function StatusBadge({ status }: { status: PinSubmission['status'] }) {
  const colors = {
    pending: 'bg-yellow-900/40 border-yellow-800 text-yellow-300',
    approved: 'bg-green-900/40 border-green-800 text-green-300',
    rejected: 'bg-red-900/40 border-red-800 text-red-300',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${colors[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export default function AdminSubmissionsPage() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<StatusFilter>('pending');
  const [submissions, setSubmissions] = useState<PinSubmission[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [exporting, setExporting] = useState(false);

  const PAGE_SIZE = 50;

  useEffect(() => {
    if (!authLoading && user === null) {
      navigate('/login', { replace: true });
    }
  }, [authLoading, user, navigate]);

  useEffect(() => {
    if (authLoading || user === null) return;
    setLoading(true);
    setSubmissions([]);
    fetchAdminSubmissions(activeTab, PAGE_SIZE, 0)
      .then((res) => {
        setIsAdmin(true);
        setSubmissions(res.submissions);
        setTotal(res.total);
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setIsAdmin(false);
          setTimeout(() => navigate('/map', { replace: true }), 2000);
        }
      })
      .finally(() => setLoading(false));
  }, [activeTab, authLoading, user, navigate]);

  async function handleLoadMore() {
    setLoadingMore(true);
    try {
      const res = await fetchAdminSubmissions(activeTab, PAGE_SIZE, submissions.length);
      setSubmissions((prev) => [...prev, ...res.submissions]);
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      await exportApprovedSubmissions();
    } finally {
      setExporting(false);
    }
  }

  if (isAdmin === false) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <p className="text-red-400 text-sm">Access denied. Redirecting…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Top nav bar */}
      <div className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-3xl mx-auto flex items-center gap-3 px-4 h-12">
          <Link
            to="/map"
            className="text-slate-400 hover:text-white transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Map
          </Link>
          <span className="text-slate-600">·</span>
          <span className="text-slate-300 text-sm font-medium">Community Submissions</span>
          <div className="flex-1" />
          <button
            onClick={handleExport}
            disabled={exporting}
            className="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
          >
            {exporting ? 'Exporting…' : 'Export Approved as JSON'}
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6">
        {/* Tab bar */}
        <div className="flex gap-1 bg-slate-900/50 border border-slate-800 rounded-2xl p-1 mb-6">
          {(['pending', 'approved', 'rejected'] as StatusFilter[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 text-sm font-medium rounded-xl transition-colors capitalize ${
                activeTab === tab
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : submissions.length === 0 ? (
          <div className="text-center py-16 text-slate-500 text-sm">
            No {activeTab} submissions.
          </div>
        ) : (
          <div className="space-y-3">
            {submissions.map((sub) => (
              <div
                key={sub.id}
                className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 space-y-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-semibold text-white text-sm truncate">{sub.name}</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      @{sub.submitter_username ?? 'unknown'} · {relativeTime(sub.submitted_at)}
                    </p>
                  </div>
                  <StatusBadge status={sub.status} />
                </div>

                {/* Type badge */}
                <div>
                  {sub.pin_type ? (
                    <span className="inline-flex text-xs bg-slate-800 border border-slate-700 text-slate-300 px-2 py-0.5 rounded-full">
                      {sub.pin_type.replace(/_/g, ' ')}
                    </span>
                  ) : sub.suggested_type ? (
                    <span className="inline-flex text-xs bg-slate-800 border border-slate-700 text-slate-400 px-2 py-0.5 rounded-full">
                      Suggested: {sub.suggested_type}
                    </span>
                  ) : (
                    <span className="inline-flex text-xs bg-slate-800 border border-slate-700 text-slate-500 px-2 py-0.5 rounded-full">
                      No type
                    </span>
                  )}
                </div>

                {/* Coordinates */}
                <p className="text-xs text-slate-400">
                  {sub.latitude.toFixed(5)}, {sub.longitude.toFixed(5)}
                </p>

                {/* Description preview */}
                {sub.description && (
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                    {sub.description}
                  </p>
                )}

                <div className="pt-1">
                  <Link
                    to={`/admin/submissions/${sub.id}`}
                    className="text-xs text-blue-400 hover:text-blue-300 transition-colors font-medium"
                  >
                    Review →
                  </Link>
                </div>
              </div>
            ))}

            {submissions.length < total && (
              <div className="text-center pt-4">
                <button
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="text-sm text-slate-400 hover:text-white transition-colors disabled:opacity-50"
                >
                  {loadingMore ? 'Loading…' : `Load more (${total - submissions.length} remaining)`}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
