import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const { signIn, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      navigate('/map', { replace: true });
    }
  }, [user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signIn(email, password);
      navigate('/map');
    } catch (err: any) {
      setError(err.message ?? 'Sign in failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-amber-50/30 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white border border-stone-200 rounded-2xl p-8 shadow-sm">
        <div className="flex items-center gap-2 mb-6">
          <span className="text-2xl">🗺️</span>
          <h1 className="text-stone-900 text-xl font-bold">Prescia Maps</h1>
        </div>
        <h2 className="text-stone-800 text-lg font-semibold mb-6">Sign in to your account</h2>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-stone-600 text-sm mb-1" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-stone-600 text-sm mb-1" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-stone-800 hover:bg-stone-700 disabled:opacity-50 text-white font-semibold py-2 rounded-xl transition-colors text-sm"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-4 text-center text-stone-500 text-sm">
          Don't have an account?{' '}
          <Link to="/signup" className="text-amber-700 hover:text-amber-600">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
