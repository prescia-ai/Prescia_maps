import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// ─── Top-bar compact login ────────────────────────────────────────────────────

function TopBarLogin() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      {error && (
        <span className="text-red-600 text-xs hidden sm:block">{error}</span>
      )}
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        className="hidden sm:block w-36 lg:w-44 bg-white border border-stone-200 rounded-lg px-3 py-1.5 text-stone-900 text-sm placeholder-stone-400 focus:outline-none focus:border-stone-400"
      />
      <input
        type="password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        className="hidden sm:block w-28 lg:w-36 bg-white border border-stone-200 rounded-lg px-3 py-1.5 text-stone-900 text-sm placeholder-stone-400 focus:outline-none focus:border-stone-400"
      />
      <button
        type="submit"
        disabled={loading}
        className="hidden sm:block bg-stone-800 hover:bg-stone-700 text-white font-semibold px-4 py-1.5 rounded-lg text-sm disabled:opacity-50 transition-colors whitespace-nowrap"
      >
        {loading ? '…' : 'Log in'}
      </button>
      {/* Mobile fallback: just show a link */}
      <Link
        to="/login"
        className="sm:hidden text-stone-900 font-semibold text-sm underline underline-offset-2"
      >
        Log in
      </Link>
    </form>
  );
}

// ─── Right-column signup card ─────────────────────────────────────────────────

function SignupCard() {
  const { signUp } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

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
    <div className="bg-white border border-stone-200 rounded-3xl p-7 shadow-sm">
      <h2 className="text-stone-900 text-xl font-bold mb-1">Sign up — it's free.</h2>
      <p className="text-stone-500 text-sm mb-5">Join the community of history hunters.</p>

      {success ? (
        <div className="px-4 py-4 rounded-xl bg-green-50 border border-green-200 text-green-700 text-sm text-center">
          <p className="font-semibold">Check your email to verify your account!</p>
          <p className="mt-1 text-green-600">
            Once verified, you can{' '}
            <Link to="/login" className="underline">sign in</Link>.
          </p>
        </div>
      ) : (
        <>
          {error && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-stone-600 text-sm mb-1" htmlFor="signup-email">
                Email
              </label>
              <input
                id="signup-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-stone-600 text-sm mb-1" htmlFor="signup-password">
                Password
              </label>
              <input
                id="signup-password"
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
                placeholder="••••••••"
              />
            </div>
            <div>
              <label className="block text-stone-600 text-sm mb-1" htmlFor="signup-confirm">
                Confirm Password
              </label>
              <input
                id="signup-confirm"
                type="password"
                required
                minLength={6}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-stone-900 text-sm focus:outline-none focus:border-stone-400 placeholder-stone-400"
                placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-xl transition-colors text-sm"
            >
              {loading ? 'Creating account…' : 'Sign Up'}
            </button>
          </form>

          <p className="mt-4 text-center text-stone-500 text-sm">
            Already have an account?{' '}
            <Link to="/login" className="text-amber-700 hover:text-amber-600">
              Log in
            </Link>
          </p>
        </>
      )}
    </div>
  );
}

// ─── Main HomePage ─────────────────────────────────────────────────────────────

export default function HomePage() {
  const { user, loading } = useAuth();

  // Redirect logged-in users straight to the map
  if (!loading && user) {
    return <Navigate to="/map" replace />;
  }

  // While auth state is loading, render nothing to avoid flash
  if (loading) return null;

  return (
    <div className="min-h-screen flex flex-col bg-amber-50/30">
      {/* ── Top bar ─────────────────────────────────────────────── */}
      <header className="bg-white border-b border-stone-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          {/* Brand */}
          <div className="shrink-0">
            <img
              src="/brand/logo.png"
              alt="Aurik logo"
              className="h-8 w-auto"
            />
          </div>

          {/* Compact login */}
          <TopBarLogin />
        </div>
      </header>

      {/* ── Hero section ────────────────────────────────────────── */}
      <main className="flex-1">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 md:py-20">
          <div className="grid grid-cols-1 md:grid-cols-[55%_45%] gap-10 md:gap-14 items-start">

            {/* Left: marketing copy */}
            <div>
              <h1 className="text-4xl sm:text-5xl font-extrabold text-stone-900 leading-tight mb-4">
                Map the past.<br />
                <span className="text-amber-700">Hunt the present.</span>
              </h1>
              <p className="text-stone-600 text-lg leading-relaxed mb-8 max-w-prose">
                Aurik is the community map for metal-detecting hobbyists and history
                researchers. Overlay vintage aerial imagery, log your hunts, discover
                ghost towns, and collaborate with a growing community of field historians.
              </p>

              {/* Feature bullets */}
              <ul className="space-y-4 mb-6">
                <li className="flex items-start gap-3">
                  <span className="text-2xl leading-none mt-0.5">🗺️</span>
                  <div>
                    <p className="font-semibold text-stone-900">Map every site</p>
                    <p className="text-stone-500 text-sm">
                      Pin ghost towns, abandoned structures, and historic finds on a shared
                      live map with vintage aerial overlays.
                    </p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-2xl leading-none mt-0.5">📓</span>
                  <div>
                    <p className="font-semibold text-stone-900">Log every hunt</p>
                    <p className="text-stone-500 text-sm">
                      Keep a personal field journal, track your finds, and build a private
                      archive of your expeditions.
                    </p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-2xl leading-none mt-0.5">👥</span>
                  <div>
                    <p className="font-semibold text-stone-900">Join the community</p>
                    <p className="text-stone-500 text-sm">
                      Follow fellow hunters, share discoveries, and earn badges as you
                      contribute to the collective record.
                    </p>
                  </div>
                </li>
              </ul>

            </div>

            {/* Right: signup card */}
            <div className="md:sticky md:top-8">
              <SignupCard />
            </div>
          </div>
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer className="border-t border-stone-200 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 flex flex-wrap gap-x-6 gap-y-2 justify-center text-stone-400 text-xs">
          <a href="/about" className="hover:text-stone-600 transition-colors">About</a>
          <a href="#" className="hover:text-stone-600 transition-colors">Privacy</a>
          <a href="#" className="hover:text-stone-600 transition-colors">Terms</a>
          <a href="#" className="hover:text-stone-600 transition-colors">Contact</a>
          <span>© {new Date().getFullYear()} Aurik</span>
        </div>
      </footer>
    </div>
  );
}
