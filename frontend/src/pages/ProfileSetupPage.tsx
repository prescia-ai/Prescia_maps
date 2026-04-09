import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';

export default function ProfileSetupPage() {
  const { user, profile, refreshProfile } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [location, setLocation] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
        display_name: displayName || undefined,
        bio: bio || undefined,
        location: location || undefined,
      });
      await refreshProfile();
      navigate('/map');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to set up profile');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-2xl p-8 shadow-2xl">
        <div className="flex items-center gap-2 mb-6">
          <span className="text-2xl">🗺️</span>
          <h1 className="text-white text-xl font-bold">Prescia Maps</h1>
        </div>
        <h2 className="text-slate-200 text-lg font-semibold mb-2">Set up your profile</h2>
        <p className="text-slate-400 text-sm mb-6">Choose a username to get started.</p>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-lg bg-red-900/40 border border-red-700 text-red-300 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-slate-400 text-sm mb-1" htmlFor="username">
              Username <span className="text-red-400">*</span>
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
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-slate-400 placeholder-slate-500"
              placeholder="cool_detector"
            />
            <p className="text-slate-500 text-xs mt-1">3–30 characters, letters, numbers and underscores only</p>
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1" htmlFor="displayName">
              Display Name
            </label>
            <input
              id="displayName"
              type="text"
              maxLength={100}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-slate-400 placeholder-slate-500"
              placeholder="Your Name"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1" htmlFor="bio">
              Bio
            </label>
            <textarea
              id="bio"
              rows={3}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-slate-400 placeholder-slate-500 resize-none"
              placeholder="Tell the community about yourself…"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1" htmlFor="location">
              Location
            </label>
            <input
              id="location"
              type="text"
              maxLength={100}
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-slate-400 placeholder-slate-500"
              placeholder="City, State"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-2 rounded-lg transition-colors text-sm"
          >
            {loading ? 'Saving…' : 'Save and continue'}
          </button>
        </form>
      </div>
    </div>
  );
}
