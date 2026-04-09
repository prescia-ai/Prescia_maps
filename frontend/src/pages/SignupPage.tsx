import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function SignupPage() {
  const { signUp, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      navigate('/map', { replace: true });
    }
  }, [user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      await signUp(email, password);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message ?? 'Sign up failed');
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
        <h2 className="text-slate-200 text-lg font-semibold mb-6">Create an account</h2>

        {success ? (
          <div className="px-4 py-4 rounded-lg bg-green-900/40 border border-green-700 text-green-300 text-sm text-center">
            <p className="font-semibold">Check your email to verify your account!</p>
            <p className="mt-1 text-green-400">Once verified, you can{' '}
              <Link to="/login" className="underline">sign in</Link>.
            </p>
          </div>
        ) : (
          <>
            {error && (
              <div className="mb-4 px-4 py-3 rounded-lg bg-red-900/40 border border-red-700 text-red-300 text-sm">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-slate-400 text-sm mb-1" htmlFor="email">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-slate-400 placeholder-slate-500"
                  placeholder="you@example.com"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-slate-400 placeholder-slate-500"
                  placeholder="••••••••"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1" htmlFor="confirm">
                  Confirm Password
                </label>
                <input
                  id="confirm"
                  type="password"
                  required
                  minLength={6}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-slate-400 placeholder-slate-500"
                  placeholder="••••••••"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-2 rounded-lg transition-colors text-sm"
              >
                {loading ? 'Creating account…' : 'Create account'}
              </button>
            </form>

            <p className="mt-4 text-center text-slate-400 text-sm">
              Already have an account?{' '}
              <Link to="/login" className="text-blue-400 hover:text-blue-300">
                Sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
