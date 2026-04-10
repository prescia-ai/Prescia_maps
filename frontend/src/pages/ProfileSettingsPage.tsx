import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api, { disconnectGoogle, fetchGoogleAuthUrl } from '../api/client';

const BIO_MAX = 250;

export default function ProfileSettingsPage() {
  const { user, profile, loading: authLoading, refreshProfile } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [location, setLocation] = useState('');
  const [privacy, setPrivacy] = useState<'public' | 'friends' | 'private'>('public');

  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [googleSuccess, setGoogleSuccess] = useState(false);
  const [googleError, setGoogleError] = useState(false);
  const [connectingGoogle, setConnectingGoogle] = useState(false);
  const [disconnectingGoogle, setDisconnectingGoogle] = useState(false);

  // Redirect if not logged in (only after auth has finished loading)
  useEffect(() => {
    if (!authLoading && user === null) {
      navigate('/login', { replace: true });
    }
  }, [authLoading, user, navigate]);

  // Pre-fill form with existing profile data
  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name ?? '');
      setBio(profile.bio ?? '');
      setLocation(profile.location ?? '');
      setPrivacy((profile.privacy as 'public' | 'friends' | 'private') ?? 'public');
    }
  }, [profile]);

  // Handle Google OAuth callback query params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const googleParam = params.get('google');
    if (googleParam === 'connected') {
      setGoogleSuccess(true);
      refreshProfile();
      setTimeout(() => setGoogleSuccess(false), 5000);
    } else if (googleParam === 'error') {
      setGoogleError(true);
      setTimeout(() => setGoogleError(false), 5000);
    }
    if (googleParam) {
      window.history.replaceState({}, '', window.location.pathname);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleConnectGoogle() {
    setConnectingGoogle(true);
    try {
      const url = await fetchGoogleAuthUrl();
      window.location.href = url;
    } catch {
      setGoogleError(true);
      setTimeout(() => setGoogleError(false), 5000);
      setConnectingGoogle(false);
    }
  }

  async function handleDisconnectGoogle() {
    const confirmed = window.confirm(
      "Disconnect Google Drive? You won't be able to upload photos until you reconnect.",
    );
    if (!confirmed) return;
    setDisconnectingGoogle(true);
    try {
      await disconnectGoogle();
      await refreshProfile();
    } catch {
      setGoogleError(true);
      setTimeout(() => setGoogleError(false), 5000);
    } finally {
      setDisconnectingGoogle(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      await api.put('/auth/profile', {
        display_name: displayName || null,
        bio: bio || null,
        location: location || null,
        privacy,
      });
      await refreshProfile();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to save. Please try again.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Top nav bar */}
      <div className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm">
        <div className="max-w-2xl mx-auto flex items-center gap-3 px-4 h-12">
          <Link
            to={profile?.username ? `/profile/${profile.username}` : '/map'}
            className="text-slate-400 hover:text-white transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Profile
          </Link>
          <span className="text-slate-600">·</span>
          <span className="text-slate-400 text-sm">Edit Profile</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-xl font-semibold text-white mb-6">Edit Profile</h1>

        {/* Success toast */}
        {success && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-green-900/40 border border-green-800 text-green-300 text-sm flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Profile saved!
          </div>
        )}

        {/* Error toast */}
        {error && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-red-900/40 border border-red-800 text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* Google Drive success toast */}
        {googleSuccess && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-green-900/40 border border-green-800 text-green-300 text-sm flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Google Drive connected!
          </div>
        )}

        {/* Google Drive error toast */}
        {googleError && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-red-900/40 border border-red-800 text-red-300 text-sm">
            Failed to connect Google Drive. Please try again.
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          {/* Profile info card */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-6 space-y-5">
            {/* Display Name */}
            <div className="space-y-1.5">
              <label htmlFor="displayName" className="block text-sm font-medium text-slate-300">
                Display Name
              </label>
              <input
                id="displayName"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                maxLength={100}
                placeholder="Your name"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* Bio */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="bio" className="block text-sm font-medium text-slate-300">
                  Bio
                </label>
                <span className={`text-xs ${bio.length > BIO_MAX * 0.9 ? 'text-amber-400' : 'text-slate-500'}`}>
                  {bio.length}/{BIO_MAX}
                </span>
              </div>
              <textarea
                id="bio"
                value={bio}
                onChange={(e) => setBio(e.target.value.slice(0, BIO_MAX))}
                rows={3}
                placeholder="Tell people about yourself..."
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 transition-colors resize-none"
              />
            </div>

            {/* Location */}
            <div className="space-y-1.5">
              <label htmlFor="location" className="block text-sm font-medium text-slate-300">
                Location
              </label>
              <input
                id="location"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                maxLength={100}
                placeholder="City, State"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            {/* Privacy */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-300">Privacy</label>
              <div className="flex rounded-xl overflow-hidden border border-slate-700">
                {(['public', 'friends', 'private'] as const).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setPrivacy(opt)}
                    className={`flex-1 py-2 text-xs font-medium capitalize transition-colors ${
                      privacy === opt
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'
                    }`}
                  >
                    {opt === 'friends' ? 'Friends Only' : opt.charAt(0).toUpperCase() + opt.slice(1)}
                  </button>
                ))}
              </div>
              <p className="text-xs text-slate-500">
                {privacy === 'public' && 'Anyone can view your full profile.'}
                {privacy === 'friends' && 'Only friends can view your full profile.'}
                {privacy === 'private' && 'Only your name and join date are visible to others.'}
              </p>
            </div>
          </div>

          {/* Google Drive section */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-6">
            <h2 className="text-sm font-semibold text-slate-200 mb-1">Google Drive</h2>
            <p className="text-xs text-slate-500 mb-4">
              Connect your Google Drive to upload profile pictures and find photos.
            </p>
            {profile?.google_email && profile?.google_connected_at ? (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-green-400 text-sm">
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  <span>
                    Connected as <span className="font-medium">{profile.google_email}</span>
                    <span className="text-slate-500 text-xs ml-1">
                      · {new Date(profile.google_connected_at).toLocaleDateString()}
                    </span>
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleDisconnectGoogle}
                  disabled={disconnectingGoogle}
                  className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {disconnectingGoogle ? 'Disconnecting…' : 'Disconnect'}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={handleConnectGoogle}
                disabled={connectingGoogle}
                className="bg-slate-800 border border-slate-700 text-slate-200 hover:text-white hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium py-2 px-4 rounded-xl transition-colors flex items-center gap-2 text-sm"
              >
                {connectingGoogle ? (
                  <>
                    <span className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
                    Redirecting…
                  </>
                ) : (
                  'Connect Google Drive'
                )}
              </button>
            )}
          </div>

          {/* Actions */}
          <button
            type="submit"
            disabled={saving}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 rounded-2xl transition-colors flex items-center justify-center gap-2 text-sm"
          >
            {saving ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Saving…
              </>
            ) : (
              'Save Changes'
            )}
          </button>

          <div className="text-center">
            <Link
              to={profile?.username ? `/profile/${profile.username}` : '/map'}
              className="text-sm text-slate-400 hover:text-slate-300 transition-colors"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
