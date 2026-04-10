import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api, { fetchGoogleAuthUrl } from '../api/client';

export default function ProfileSetupPage() {
  const { user, profile, refreshProfile } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2>(1);
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [location, setLocation] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [connectingGoogle, setConnectingGoogle] = useState(false);

  useEffect(() => {
    if (!user) {
      navigate('/login', { replace: true });
    } else if (profile?.username) {
      navigate('/map', { replace: true });
    }
  }, [user, profile, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.put('/auth/profile-setup', {
        username,
        display_name: displayName,
        bio: bio || undefined,
        location: location || undefined,
      });
      await refreshProfile();
      setStep(2);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to set up profile');
    } finally {
      setLoading(false);
    }
  };

  async function handleConnectGoogle() {
    setConnectingGoogle(true);
    try {
      const url = await fetchGoogleAuthUrl();
      window.location.href = url;
    } catch {
      setConnectingGoogle(false);
    }
  }

  if (step === 2) {
    return (
      <div className="min-h-screen bg-amber-50/30 flex items-center justify-center px-4">
        <div className="w-full max-w-md bg-white border border-stone-200 rounded-2xl p-8 shadow-sm">
          <div className="flex items-center gap-2 mb-6">
            <span className="text-2xl">🗺️</span>
            <h1 className="text-stone-900 text-xl font-bold">Prescia Maps</h1>
          </div>
          <h2 className="text-stone-800 text-lg font-semibold mb-2">Connect Google Drive</h2>
          <p className="text-stone-500 text-sm mb-6">
            Connect Google Drive to upload profile photos, post images, and hunt photos. You can always do this later in your profile settings.
          </p>

          <div className="space-y-3">
            <button
              onClick={handleConnectGoogle}
              disabled={connectingGoogle}
              className="w-full flex items-center justify-center gap-2 bg-white border border-stone-300 hover:border-stone-400 hover:bg-stone-50 disabled:opacity-50 text-stone-800 font-medium py-2.5 rounded-xl transition-colors text-sm shadow-sm"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              {connectingGoogle ? 'Redirecting…' : 'Connect Google Drive'}
            </button>

            <button
              onClick={() => navigate('/map')}
              className="w-full text-sm text-stone-500 hover:text-stone-700 py-2 transition-colors"
            >
              Skip for now → Go to Map
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-amber-50/30 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white border border-stone-200 rounded-2xl p-8 shadow-sm">
        <div className="flex items-center gap-2 mb-6">
          <span className="text-2xl">🗺️</span>
          <h1 className="text-stone-900 text-xl font-bold">Prescia Maps</h1>
        </div>
        <h2 className="text-stone-800 text-lg font-semibold mb-2">Set up your profile</h2>
        <p className="text-stone-500 text-sm mb-6">Choose a username to get started.</p>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-stone-600 text-sm mb-1" htmlFor="username">
              Username <span className="text-red-500">*</span>
            </label>
            <input
              id="username"
              type="text"
              required
              minLength={3}
              maxLength={30}
              pattern="^[a-zA-Z0-9_]+$"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
              placeholder="cool_detector"
            />
            <p className="text-stone-400 text-xs mt-1">3–30 characters, letters, numbers and underscores only</p>
          </div>
          <div>
            <label className="block text-stone-600 text-sm mb-1" htmlFor="displayName">
              Display Name <span className="text-red-500">*</span>
            </label>
            <input
              id="displayName"
              type="text"
              required
              maxLength={100}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
              placeholder="Your Name"
            />
          </div>
          <div>
            <label className="block text-stone-600 text-sm mb-1" htmlFor="bio">
              Bio
            </label>
            <textarea
              id="bio"
              rows={3}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400 resize-none"
              placeholder="Tell the community about yourself…"
            />
          </div>
          <div>
            <label className="block text-stone-600 text-sm mb-1" htmlFor="location">
              Location
            </label>
            <input
              id="location"
              type="text"
              maxLength={100}
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
              placeholder="City, State"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-50 text-white font-semibold py-2 rounded-xl transition-colors text-sm"
          >
            {loading ? 'Saving…' : 'Save and continue'}
          </button>
        </form>
      </div>
    </div>
  );
}
