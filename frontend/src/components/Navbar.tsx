import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Avatar from './Avatar';
import { searchUsers } from '../api/client';

function UserSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Array<{ username: string; display_name: string | null; avatar_url: string | null }>>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Close when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Close on Escape key
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, []);

  // Debounced search
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const data = await searchUsers(query.trim());
        setResults(data);
        setOpen(true);
      } catch {
        setResults([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  function handleSelect(username: string) {
    setOpen(false);
    setQuery('');
    navigate(`/profile/${username}`);
  }

  return (
    <div ref={ref} className="relative hidden sm:block">
      <div className="relative">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-stone-400 pointer-events-none">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search users…"
          className="w-48 bg-stone-100 border border-stone-200 rounded-lg pl-7 pr-3 py-1.5 text-xs text-stone-700 placeholder-stone-400 focus:outline-none focus:border-stone-400 transition-colors"
        />
      </div>
      {open && (
        <div className="absolute top-full mt-1 w-64 bg-white border border-stone-200 rounded-xl shadow-lg z-50 py-1 max-h-64 overflow-y-auto">
          {results.length === 0 ? (
            <div className="px-3 py-2 text-sm text-stone-400">No users found</div>
          ) : (
            results.map((user) => (
              <button
                key={user.username}
                onClick={() => handleSelect(user.username)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-stone-50 cursor-pointer transition-colors text-left"
              >
                <Avatar
                  username={user.username}
                  displayName={user.display_name ?? undefined}
                  avatarUrl={user.avatar_url ?? undefined}
                  size="sm"
                />
                <div className="flex flex-col min-w-0">
                  <span className="text-stone-800 font-medium text-xs truncate">{user.username}</span>
                  {user.display_name && (
                    <span className="text-stone-400 text-xs truncate">{user.display_name}</span>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

interface NavbarProps {
  locationCount: number;
  isLoading: boolean;
  isLocationsError: boolean;
  isFeaturesError: boolean;
  onImportClick: () => void;
  onLogHuntClick?: () => void;
}

function SettingsDropdown({ onSignOut, onImportClick }: { onSignOut: () => void; onImportClick: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { profile } = useAuth();

  // Close when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-center w-7 h-7 text-stone-500 hover:text-stone-800 hover:bg-stone-100 rounded-lg transition-colors"
        title="Settings"
        aria-label="Settings"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-stone-200 rounded-xl shadow-lg z-50 py-1 overflow-hidden">
          <Link
            to="/profile/settings"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50 hover:text-stone-900 transition-colors"
          >
            <svg className="w-3.5 h-3.5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            Settings
          </Link>
          <Link
            to="/settings/security"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50 hover:text-stone-900 transition-colors"
          >
            <svg className="w-3.5 h-3.5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Security
          </Link>
          <Link
            to="/submit"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50 hover:text-stone-900 transition-colors"
          >
            <svg className="w-3.5 h-3.5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Submit a Pin
          </Link>
          {profile?.is_admin && (
            <>
              <div className="border-t border-stone-100 my-1" />
              <button
                onClick={() => {
                  setOpen(false);
                  onImportClick();
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50 hover:text-stone-900 transition-colors text-left"
              >
                <svg className="w-3.5 h-3.5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5-5m0 0l5 5m-5-5v12" />
                </svg>
                Import Data
              </button>
              <Link
                to="/admin/submissions"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 px-3 py-2 text-sm text-stone-700 hover:bg-stone-50 hover:text-stone-900 transition-colors"
              >
                <svg className="w-3.5 h-3.5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                Review Submissions
              </Link>
            </>
          )}
          <div className="border-t border-stone-100 my-1" />
          <button
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50 hover:text-stone-900 transition-colors text-left"
          >
            <svg className="w-3.5 h-3.5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Log out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Navbar({
  locationCount,
  isLoading,
  isLocationsError,
  isFeaturesError,
  onImportClick,
  onLogHuntClick,
}: NavbarProps) {
  const { user, profile, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="absolute top-0 left-0 right-0 z-20 bg-white border-b border-stone-200 shadow-sm">
      <div className="flex items-center gap-3 px-4 h-12">
        {/* Branding */}
        <span className="text-xl">🗺️</span>
        <div className="hidden sm:block">
          <h1 className="text-stone-900 font-bold text-sm leading-tight tracking-wide">
            Prescia Maps
          </h1>
          <p className="text-stone-400 text-[10px] leading-tight">
            Historical Activity &amp; Metal Detecting Intelligence
          </p>
        </div>

        {/* Nav items */}
        <div className="flex items-center gap-1 ml-4">
          <Link
            to="/map"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg transition-colors"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
              />
            </svg>
            Map
          </Link>

          {user && (
            <Link
              to="/feed"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg transition-colors"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"
                />
              </svg>
              Feed
            </Link>
          )}

          {user && (
            <button
              onClick={onLogHuntClick}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg transition-colors"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
              Log a Hunt
            </button>
          )}
        </div>

        {/* User Search */}
        <UserSearch />

        {/* Status badges */}
        <div className="ml-auto flex items-center gap-2">
          {isLocationsError && (
            <span className="text-xs text-red-600 bg-red-50 border border-red-200 px-2 py-1 rounded-full">
              ⚠ Locations unavailable
            </span>
          )}
          {isFeaturesError && (
            <span className="text-xs text-red-600 bg-red-50 border border-red-200 px-2 py-1 rounded-full">
              ⚠ Features unavailable
            </span>
          )}
          {isLoading && (
            <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded-full flex items-center gap-1">
              <span className="w-3 h-3 border border-amber-600 border-t-transparent rounded-full animate-spin inline-block" />
              Loading data…
            </span>
          )}
          {!isLoading && !isLocationsError && (
            <span className="text-xs text-green-700 bg-green-50 border border-green-200 px-2 py-1 rounded-full">
              ✓ {locationCount} locations
            </span>
          )}

          {/* Auth section */}
          {user ? (
            <div className="flex items-center gap-2 border-l border-stone-200 pl-2 ml-1">
              <Link
                to={profile?.username ? `/profile/${profile.username}` : '/setup'}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-stone-700 hover:text-stone-900 hover:bg-stone-100 rounded-xl transition-colors font-medium"
              >
                <Avatar
                  username={profile?.username ?? user.email ?? 'user'}
                  displayName={profile?.display_name}
                  avatarUrl={profile?.avatar_url}
                  size="sm"
                />
                <span>Profile</span>
              </Link>
              <SettingsDropdown onSignOut={signOut} onImportClick={onImportClick} />
            </div>
          ) : (
            <div className="border-l border-stone-200 pl-2 ml-1">
              <button
                onClick={() => navigate('/login')}
                className="text-xs bg-stone-800 text-white hover:bg-stone-700 px-3 py-1.5 rounded-lg transition-colors font-medium"
              >
                Log in
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
