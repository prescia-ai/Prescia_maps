import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import AppLayout from '../components/AppLayout';

// ─── Minimal top bar for logged-out visitors ──────────────────────────────────

function GuestTopBar() {
  return (
    <header className="bg-white border-b border-stone-200 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
        <Link to="/" className="shrink-0">
          <img src="/brand/logo.png" alt="Aurik logo" className="h-8 w-auto" />
        </Link>
        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="px-4 py-1.5 rounded-lg text-sm text-stone-700 hover:bg-stone-100 transition-colors font-medium"
          >
            Log in
          </Link>
          <Link
            to="/"
            className="px-4 py-1.5 rounded-xl text-sm bg-amber-600 hover:bg-amber-700 text-white font-medium transition-colors"
          >
            Sign up
          </Link>
        </div>
      </div>
    </header>
  );
}

// ─── Page content (shared for both auth states) ───────────────────────────────

function AboutContent() {
  return (
    <div className="min-h-screen bg-amber-50/30">
      <div className="max-w-3xl mx-auto px-4 py-12">
        {/* Heading */}
        <h1 className="text-3xl font-bold text-stone-900 mb-2">About Aurik</h1>
        <p className="text-stone-500 text-base mb-8">
          A community map and field journal for history hunters everywhere.
        </p>

        {/* Section 1 — What is Aurik? */}
        <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-6 mb-4">
          <h2 className="text-lg font-semibold text-stone-900 mb-3">What is Aurik?</h2>
          <div className="space-y-3 text-stone-600 text-sm leading-relaxed">
            <p>
              Aurik is a community-driven map and field journal built for metal-detecting
              hobbyists, history hunters, and amateur historians. It brings together the
              tools you need to research, plan, and document your expeditions in one place.
            </p>
            <p>
              At its core, Aurik overlays historical aerial imagery — starting with 1955
              USGS photography, with more eras on the way — directly onto a live map of
              ghost towns, abandoned structures, and significant historic sites. See the
              landscape as it looked decades ago alongside what's there today.
            </p>
            <p>
              Whether you're chasing a lead on a long-forgotten farmstead or cataloguing
              finds from a weekend outing, Aurik gives you the context to hunt smarter and
              the journal to remember what you find.
            </p>
          </div>
        </div>

        {/* Section 2 — What can I do here? */}
        <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-6 mb-4">
          <h2 className="text-lg font-semibold text-stone-900 mb-3">What can I do here?</h2>
          <ul className="space-y-1.5">
            {[
              {
                icon: '🗺️',
                text: 'Browse a community map of historical sites, ghost towns, and abandoned structures',
              },
              {
                icon: '🛩️',
                text: (
                  <>
                    Toggle vintage aerial imagery overlays (1955 launching first, more years to follow){' '}
                    <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-1.5 py-0.5 ml-0.5">
                      Pro
                    </span>
                  </>
                ),
              },
              {
                icon: '📓',
                text: (
                  <>
                    Log your hunts in a private field journal{' '}
                    <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-1.5 py-0.5 ml-0.5">
                      Pro
                    </span>
                  </>
                ),
              },
              {
                icon: '📋',
                text: (
                  <>
                    Plan future expeditions with the Hunt Plans tool{' '}
                    <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-1.5 py-0.5 ml-0.5">
                      Pro
                    </span>
                  </>
                ),
              },
              {
                icon: '👥',
                text: (
                  <>
                    Join groups and share finds with fellow hunters{' '}
                    <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-1.5 py-0.5 ml-0.5">
                      Pro
                    </span>
                  </>
                ),
              },
              {
                icon: '📍',
                text: (
                  <>
                    Submit new pins and contribute to the historical record{' '}
                    <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-1.5 py-0.5 ml-0.5">
                      Pro
                    </span>
                  </>
                ),
              },
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-3 text-stone-600 text-sm">
                <span className="text-lg leading-none mt-0.5 shrink-0">{item.icon}</span>
                <span>{item.text}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Section 3 — Free vs. Pro */}
        <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-6 mb-4">
          <h2 className="text-lg font-semibold text-stone-900 mb-4">Free vs. Pro</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
            {/* Free */}
            <div className="bg-stone-50 border border-stone-200 rounded-2xl p-4">
              <p className="font-semibold text-stone-800 text-sm mb-2">Free</p>
              <ul className="space-y-1.5 text-stone-600 text-sm list-disc list-inside">
                <li>Browse the community map</li>
                <li>View community pins</li>
                <li>Log up to 5 hunts</li>
                <li>Modern base map only (vintage 1955+ overlays are Pro)</li>
              </ul>
            </div>
            {/* Pro */}
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
              <p className="font-semibold text-amber-800 text-sm mb-2">Pro</p>
              <ul className="space-y-1.5 text-amber-900 text-sm list-disc list-inside">
                <li>Everything in Free</li>
                <li>Vintage aerial imagery overlays (1955, more eras coming)</li>
                <li>Unlimited hunt logs (private field journal)</li>
                <li>Submit new pins to the historical record</li>
                <li>Hunt Plans (planning tool)</li>
                <li>Groups &amp; community sharing</li>
                <li>All upcoming aerial imagery layers</li>
              </ul>
            </div>
          </div>
          <Link
            to="/"
            className="inline-block bg-amber-600 hover:bg-amber-700 text-white rounded-xl px-5 py-2.5 text-sm font-medium transition-colors"
          >
            Start free trial
          </Link>
        </div>

        {/* Section 4 — Google Drive integration */}
        <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-6 mb-4">
          <h2 className="text-lg font-semibold text-stone-900 mb-3">Google Drive integration</h2>
          <div className="space-y-3 text-stone-600 text-sm leading-relaxed">
            <p>
              Aurik uses your Google Drive to store the photos you upload — profile pictures,
              post images, and hunt photos. Connecting Drive is optional and only takes a moment
              from your profile settings.
            </p>
            <p>
              <strong>Why Google Drive?</strong> It keeps your photos in <em>your</em> account,
              on storage you already own. Aurik never holds your originals on our servers — we
              only reference the files in your Drive when displaying them in the app. That means
              you stay in control of your media, your storage costs nothing extra, and you can
              revoke access at any time from your Google account settings.
            </p>
            <p>
              <strong>What we access:</strong> Aurik creates and reads files only inside a
              dedicated Aurik folder in your Drive. We don't browse, modify, or download anything
              outside that folder. You can disconnect Drive from your profile settings whenever
              you'd like.
            </p>
          </div>
        </div>

        {/* Section 5 — Why "Aurik"? */}
        <div className="bg-white border border-stone-200 rounded-3xl shadow-sm p-6 mb-4">
          <h2 className="text-lg font-semibold text-stone-900 mb-3">Why "Aurik"?</h2>
          <p className="text-stone-600 text-sm leading-relaxed">
            The name is a nod to <em>aurum</em> — Latin for gold — and the timeless pull of
            discovery that drives every hunt. It's a coined name, but it felt right for a
            tool built around finding what's hidden beneath the surface.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AboutPage() {
  const { user, loading } = useAuth();

  if (loading) return null;

  if (user) {
    return (
      <AppLayout>
        <AboutContent />
      </AppLayout>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-amber-50/30">
      <GuestTopBar />
      <AboutContent />
    </div>
  );
}
