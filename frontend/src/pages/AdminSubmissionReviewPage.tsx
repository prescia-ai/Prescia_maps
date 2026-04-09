import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchAdminSubmission, updateAdminSubmission } from '../api/client';
import type { PinSubmission } from '../types';

const LOCATION_TYPES = [
  'battle',
  'town',
  'mine',
  'camp',
  'railroad_stop',
  'trail',
  'structure',
  'event',
  'church',
  'school',
  'cemetery',
  'fairground',
  'ferry',
  'stagecoach_stop',
  'spring',
  'locale',
  'mission',
  'trading_post',
  'shipwreck',
  'pony_express',
  'abandoned_church',
  'historic_brothel',
];

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

export default function AdminSubmissionReviewPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [submission, setSubmission] = useState<PinSubmission | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  // Editable fields
  const [name, setName] = useState('');
  const [pinType, setPinType] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [dateEra, setDateEra] = useState('');
  const [description, setDescription] = useState('');
  const [sourceReference, setSourceReference] = useState('');
  const [tags, setTags] = useState('');
  const [adminNotes, setAdminNotes] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user === null) {
      navigate('/login', { replace: true });
    }
  }, [authLoading, user, navigate]);

  useEffect(() => {
    if (authLoading || user === null || !id) return;
    fetchAdminSubmission(id)
      .then((sub) => {
        setIsAdmin(true);
        setSubmission(sub);
        setName(sub.name);
        setPinType(sub.pin_type ?? '');
        setLatitude(String(sub.latitude));
        setLongitude(String(sub.longitude));
        setDateEra(sub.date_era ?? '');
        setDescription(sub.description ?? '');
        setSourceReference(sub.source_reference ?? '');
        setTags(sub.tags ?? '');
        setAdminNotes(sub.admin_notes ?? '');
        setRejectionReason(sub.rejection_reason ?? '');
      })
      .catch((err) => {
        if (err?.response?.status === 403) {
          setIsAdmin(false);
          setTimeout(() => navigate('/map', { replace: true }), 2000);
        } else {
          setError('Submission not found.');
        }
      })
      .finally(() => setLoading(false));
  }, [authLoading, user, id, navigate]);

  function buildPayload(statusOverride?: 'pending' | 'approved' | 'rejected') {
    return {
      name: name || undefined,
      pin_type: pinType || null,
      latitude: parseFloat(latitude) || undefined,
      longitude: parseFloat(longitude) || undefined,
      date_era: dateEra || null,
      description: description || null,
      source_reference: sourceReference || null,
      tags: tags || null,
      admin_notes: adminNotes || null,
      rejection_reason: rejectionReason || null,
      status: statusOverride,
    };
  }

  async function handleSaveDraft() {
    setError(null);
    setSuccessMsg(null);
    setSaving(true);
    try {
      const updated = await updateAdminSubmission(id!, buildPayload());
      setSubmission(updated);
      setSuccessMsg('Draft saved.');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Save failed.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  async function handleReject() {
    if (!rejectionReason.trim()) {
      setError('Please add a rejection reason before rejecting.');
      return;
    }
    setError(null);
    setSuccessMsg(null);
    setSaving(true);
    try {
      const updated = await updateAdminSubmission(id!, buildPayload('rejected'));
      setSubmission(updated);
      setSuccessMsg('Submission rejected.');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Rejection failed.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  async function handleApprove() {
    if (!pinType) {
      setError('You must select a Pin Type before approving.');
      return;
    }
    if (!window.confirm('This will add the pin to the live map. Continue?')) return;
    setError(null);
    setSuccessMsg(null);
    setSaving(true);
    try {
      const updated = await updateAdminSubmission(id!, buildPayload('approved'));
      setSubmission(updated);
      setSuccessMsg('Submission approved and added to the map!');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Approval failed.';
      setError(msg);
    } finally {
      setSaving(false);
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
        <div className="max-w-2xl mx-auto flex items-center gap-3 px-4 h-12">
          <Link
            to="/admin/submissions"
            className="text-slate-400 hover:text-white transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Submissions
          </Link>
          <span className="text-slate-600">·</span>
          <span className="text-slate-400 text-sm truncate">{submission?.name ?? 'Review'}</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : !submission ? (
          <p className="text-slate-400 text-sm">{error ?? 'Submission not found.'}</p>
        ) : (
          <>
            {/* Submitter info */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 mb-6 text-sm space-y-1">
              <p className="text-slate-300">
                <span className="text-slate-500">Submitted by</span>{' '}
                <span className="font-medium">@{submission.submitter_username ?? 'unknown'}</span>
              </p>
              <p className="text-slate-400">
                {relativeTime(submission.submitted_at)}
              </p>
              <p className="text-slate-400">
                Status:{' '}
                <span className={
                  submission.status === 'approved' ? 'text-green-400' :
                  submission.status === 'rejected' ? 'text-red-400' :
                  'text-yellow-400'
                }>
                  {submission.status}
                </span>
              </p>
            </div>

            {successMsg && (
              <div className="mb-4 px-4 py-3 rounded-2xl bg-green-900/40 border border-green-800 text-green-300 text-sm">
                {successMsg}
              </div>
            )}
            {error && (
              <div className="mb-4 px-4 py-3 rounded-2xl bg-red-900/40 border border-red-800 text-red-300 text-sm">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-6 space-y-5">
                <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                  Submission Details
                </h2>

                {/* Name */}
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-300">Location Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value.slice(0, 200))}
                    maxLength={200}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>

                {/* Pin Type */}
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-300">Pin Type</label>
                  <select
                    value={pinType}
                    onChange={(e) => setPinType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  >
                    <option value="">-- Select type --</option>
                    {LOCATION_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                      </option>
                    ))}
                  </select>
                  {submission.suggested_type && (
                    <p className="text-xs text-slate-400">
                      User suggested: <span className="text-slate-300">{submission.suggested_type}</span>
                    </p>
                  )}
                </div>

                {/* Coordinates */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-slate-300">Latitude</label>
                    <input
                      type="number"
                      step="any"
                      value={latitude}
                      onChange={(e) => setLatitude(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-slate-300">Longitude</label>
                    <input
                      type="number"
                      step="any"
                      value={longitude}
                      onChange={(e) => setLongitude(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                </div>

                {/* Date/Era */}
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-300">Date / Era</label>
                  <input
                    type="text"
                    value={dateEra}
                    onChange={(e) => setDateEra(e.target.value.slice(0, 100))}
                    maxLength={100}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>

                {/* Description */}
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-300">Description</label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={5}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors resize-none"
                  />
                </div>

                {/* Source/Reference */}
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-300">Source / Reference</label>
                  <input
                    type="text"
                    value={sourceReference}
                    onChange={(e) => setSourceReference(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>

                {/* Tags */}
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-300">Tags</label>
                  <input
                    type="text"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
              </div>

              {/* Admin-only fields */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-6 space-y-5">
                <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                  Admin Fields
                </h2>

                {/* Admin Notes */}
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-300">
                    Admin Notes <span className="text-slate-500 font-normal">(private)</span>
                  </label>
                  <textarea
                    value={adminNotes}
                    onChange={(e) => setAdminNotes(e.target.value)}
                    rows={3}
                    placeholder="Internal notes — user will never see these"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 transition-colors resize-none"
                  />
                </div>

                {/* Rejection Reason */}
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-slate-300">
                    Rejection Reason <span className="text-slate-500 font-normal">(visible to submitter)</span>
                  </label>
                  <textarea
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    rows={3}
                    placeholder="Explain why the submission was rejected (required when rejecting)"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 transition-colors resize-none"
                  />
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex flex-col gap-3 pt-2">
                <button
                  onClick={handleApprove}
                  disabled={saving || submission.status === 'approved'}
                  className="w-full bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 rounded-2xl transition-colors text-sm"
                >
                  {saving ? 'Saving…' : 'Approve & Add to Map'}
                </button>

                <div className="flex gap-3">
                  <button
                    onClick={handleSaveDraft}
                    disabled={saving}
                    className="flex-1 bg-transparent hover:bg-slate-800 border border-slate-700 text-slate-300 font-medium py-3 rounded-2xl transition-colors text-sm"
                  >
                    Save Draft
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={saving || submission.status === 'rejected'}
                    className="flex-1 bg-red-900/40 hover:bg-red-900/60 border border-red-800 text-red-300 disabled:opacity-50 disabled:cursor-not-allowed font-medium py-3 rounded-2xl transition-colors text-sm"
                  >
                    Reject
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
