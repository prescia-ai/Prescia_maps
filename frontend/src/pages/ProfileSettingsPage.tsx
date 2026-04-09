import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';

const BIO_MAX = 250;

export default function ProfileSettingsPage() {
  const { user, profile, refreshProfile } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [location, setLocation] = useState('');
  const [privacy, setPrivacy] = useState<'public' | 'friends' | 'private'>('public');

  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect if not logged in
  useEffect(() => {
    if (user === null) {
      navigate('/login', { replace: true });
    }
  }, [user, navigate]);

  // Pre-fill form with existing profile data
  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name ?? '');
      setBio(profile.bio ?? '');
      setLocation(profile.location ?? '');
      setPrivacy((profile.privacy as 'public' | 'friends' | 'private') ?? 'public');
    }
  }, [profile]);

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
