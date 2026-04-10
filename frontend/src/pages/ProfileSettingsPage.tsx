import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Avatar from '../components/Avatar';
import api, { disconnectGoogle, fetchGoogleAuthUrl, uploadAvatar, deleteAvatar } from '../api/client';
import { resizeImage } from '../utils/imageResize';

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

  // Avatar upload state
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarSuccess, setAvatarSuccess] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const [removingAvatar, setRemovingAvatar] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  async function handleAvatarFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setAvatarUploading(true);
    setAvatarError(null);
    setAvatarSuccess(false);

    try {
      // Client-side resize to max 400x400
      const resizedFile = await resizeImage(file, 400, 400);
      await uploadAvatar(resizedFile);
      await refreshProfile();
      setAvatarSuccess(true);
      setTimeout(() => setAvatarSuccess(false), 3000);
    } catch {
      setAvatarError('Failed to upload photo. Please try again.');
      setTimeout(() => setAvatarError(null), 5000);
    } finally {
      setAvatarUploading(false);
      // Reset file input so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleRemoveAvatar() {
    setRemovingAvatar(true);
    try {
      await deleteAvatar();
      await refreshProfile();
    } catch {
      setAvatarError('Failed to remove photo. Please try again.');
      setTimeout(() => setAvatarError(null), 5000);
    } finally {
      setRemovingAvatar(false);
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
    <div className="min-h-screen bg-stone-50 text-stone-900">
      {/* Top nav bar */}
      <div className="border-b border-stone-200 bg-white shadow-sm">
        <div className="max-w-2xl mx-auto flex items-center gap-3 px-4 h-12">
          <Link
            to={profile?.username ? `/profile/${profile.username}` : '/map'}
            className="text-stone-500 hover:text-stone-900 transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Profile
          </Link>
          <span className="text-stone-300">·</span>
          <span className="text-stone-500 text-sm">Edit Profile</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-xl font-semibold text-stone-900 mb-6">Edit Profile</h1>

        {/* Success toast */}
        {success && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-green-50 border border-green-200 text-green-700 text-sm flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Profile saved!
          </div>
        )}

        {/* Error toast */}
        {error && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Google Drive success toast */}
        {googleSuccess && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-green-50 border border-green-200 text-green-700 text-sm flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Google Drive connected!
          </div>
        )}

        {/* Google Drive error toast */}
        {googleError && (
          <div className="mb-4 px-4 py-3 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm">
            Failed to connect Google Drive. Please try again.
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          {/* Avatar upload card */}
          <div className="bg-white border border-stone-200 rounded-3xl p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-stone-700 mb-4">Profile Photo</h2>

            {/* Avatar success toast */}
            {avatarSuccess && (
              <div className="mb-4 px-4 py-3 rounded-2xl bg-green-50 border border-green-200 text-green-700 text-sm flex items-center gap-2">
                <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                Profile photo updated!
              </div>
            )}

            {/* Avatar error toast */}
            {avatarError && (
              <div className="mb-4 px-4 py-3 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-sm">
                {avatarError}
              </div>
            )}

            <div className="flex items-center gap-5">
              {/* Current avatar with loading overlay */}
              <div className="relative flex-shrink-0">
                <Avatar
                  username={profile?.username ?? ''}
                  displayName={profile?.display_name}
                  avatarUrl={profile?.avatar_url}
                  size="xl"
                />
                {avatarUploading && (
                  <div className="absolute inset-0 bg-black/50 rounded-full flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
              </div>

              <div className="space-y-2">
                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={handleAvatarFileChange}
                />

                {/* Upload button */}
                <button
                  type="button"
                  disabled={!profile?.google_connected_at || avatarUploading}
                  onClick={() => fileInputRef.current?.click()}
                  title={!profile?.google_connected_at ? 'Connect Google Drive first' : undefined}
                  className="bg-white border border-stone-300 text-stone-700 hover:text-stone-900 hover:bg-stone-50 hover:border-stone-400 disabled:opacity-50 disabled:cursor-not-allowed font-medium py-2 px-4 rounded-xl transition-colors flex items-center gap-2 text-sm"
                >
                  {avatarUploading ? (
                    <>
                      <span className="w-4 h-4 border-2 border-stone-400 border-t-transparent rounded-full animate-spin" />
                      Uploading…
                    </>
                  ) : (
                    profile?.avatar_url ? 'Change Photo' : 'Upload Photo'
                  )}
                </button>

                {/* Connect Drive hint when not connected */}
                {!profile?.google_connected_at && (
                  <p className="text-xs text-stone-400">
                    <a href="#google-drive" className="text-amber-700 hover:text-amber-600 underline">Connect Google Drive</a> to upload a photo.
                  </p>
                )}

                {/* Remove button */}
                {profile?.avatar_url && (
                  <button
                    type="button"
                    disabled={removingAvatar || avatarUploading}
                    onClick={handleRemoveAvatar}
                    className="text-xs text-red-600 hover:text-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {removingAvatar ? 'Removing…' : 'Remove'}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Profile info card */}
          <div className="bg-white border border-stone-200 rounded-3xl p-6 space-y-5 shadow-sm">
            {/* Display Name */}
            <div className="space-y-1.5">
              <label htmlFor="displayName" className="block text-sm font-medium text-stone-700">
                Display Name
              </label>
              <input
                id="displayName"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                maxLength={100}
                placeholder="Your name"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
              />
            </div>

            {/* Bio */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="bio" className="block text-sm font-medium text-stone-700">
                  Bio
                </label>
                <span className={`text-xs ${bio.length > BIO_MAX * 0.9 ? 'text-amber-600' : 'text-stone-400'}`}>
                  {bio.length}/{BIO_MAX}
                </span>
              </div>
              <textarea
                id="bio"
                value={bio}
                onChange={(e) => setBio(e.target.value.slice(0, BIO_MAX))}
                rows={3}
                placeholder="Tell people about yourself..."
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors resize-none"
              />
            </div>

            {/* Location */}
            <div className="space-y-1.5">
              <label htmlFor="location" className="block text-sm font-medium text-stone-700">
                Location
              </label>
              <input
                id="location"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                maxLength={100}
                placeholder="City, State"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-4 py-2.5 text-stone-900 placeholder-stone-400 text-sm focus:outline-none focus:border-stone-400 transition-colors"
              />
            </div>

            {/* Privacy */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-stone-700">Privacy</label>
              <div className="flex rounded-xl overflow-hidden border border-stone-200">
                {(['public', 'friends', 'private'] as const).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setPrivacy(opt)}
                    className={`flex-1 py-2 text-xs font-medium capitalize transition-colors ${
                      privacy === opt
                        ? 'bg-stone-800 text-white'
                        : 'bg-white text-stone-500 hover:text-stone-700 hover:bg-stone-50'
                    }`}
                  >
                    {opt === 'friends' ? 'Friends Only' : opt.charAt(0).toUpperCase() + opt.slice(1)}
                  </button>
                ))}
              </div>
              <p className="text-xs text-stone-400">
                {privacy === 'public' && 'Anyone can view your full profile.'}
                {privacy === 'friends' && 'Only friends can view your full profile.'}
                {privacy === 'private' && 'Only your name and join date are visible to others.'}
              </p>
            </div>
          </div>

          {/* Google Drive section */}
          <div id="google-drive" className="bg-white border border-stone-200 rounded-3xl p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-stone-700 mb-1">Google Drive</h2>
            <p className="text-xs text-stone-400 mb-4">
              Connect your Google Drive to upload profile pictures and find photos.
            </p>
            {profile?.google_email && profile?.google_connected_at ? (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-green-700 text-sm">
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  <span>
                    Connected as <span className="font-medium">{profile.google_email}</span>
                    <span className="text-stone-400 text-xs ml-1">
                      · {new Date(profile.google_connected_at).toLocaleDateString()}
                    </span>
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleDisconnectGoogle}
                  disabled={disconnectingGoogle}
                  className="text-xs text-red-600 hover:text-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {disconnectingGoogle ? 'Disconnecting…' : 'Disconnect'}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={handleConnectGoogle}
                disabled={connectingGoogle}
                className="bg-white border border-stone-300 text-stone-700 hover:text-stone-900 hover:bg-stone-50 hover:border-stone-400 disabled:opacity-50 disabled:cursor-not-allowed font-medium py-2 px-4 rounded-xl transition-colors flex items-center gap-2 text-sm"
              >
                {connectingGoogle ? (
                  <>
                    <span className="w-4 h-4 border-2 border-stone-400 border-t-transparent rounded-full animate-spin" />
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
            className="w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 rounded-2xl transition-colors flex items-center justify-center gap-2 text-sm"
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
              className="text-sm text-stone-400 hover:text-stone-600 transition-colors"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
