import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Avatar from './Avatar';

interface NavbarProps {
  locationCount: number;
  isLoading: boolean;
  isLocationsError: boolean;
  isFeaturesError: boolean;
  onImportClick: () => void;
}

export default function Navbar({
  locationCount,
  isLoading,
  isLocationsError,
  isFeaturesError,
  onImportClick,
}: NavbarProps) {
  const { user, profile, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="absolute top-0 left-0 right-0 z-20 bg-slate-900/95 backdrop-blur-sm border-b border-slate-700">
      <div className="flex items-center gap-3 px-4 h-12">
        {/* Branding */}
        <span className="text-xl">🗺️</span>
        <div className="hidden sm:block">
          <h1 className="text-white font-bold text-sm leading-tight tracking-wide">
            Prescia Maps
          </h1>
          <p className="text-slate-400 text-[10px] leading-tight">
            Historical Activity &amp; Metal Detecting Intelligence
          </p>
        </div>

        {/* Nav items */}
        <div className="flex items-center gap-2 ml-4">
          <Link
            to="/feed"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-slate-700/60 rounded-lg transition-colors"
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

          <button
            onClick={onImportClick}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-slate-700/60 rounded-lg transition-colors"
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
                d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5-5m0 0l5 5m-5-5v12"
              />
            </svg>
            Import Data
          </button>

          {user && (
            <Link
              to="/submit"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-slate-700/60 rounded-lg transition-colors"
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
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Submit a Pin
            </Link>
          )}
        </div>

        {/* Status badges */}
        <div className="ml-auto flex items-center gap-2">
          {isLocationsError && (
            <span className="text-xs text-red-400 bg-red-900/40 px-2 py-1 rounded-full">
              ⚠ Locations unavailable
            </span>
          )}
          {isFeaturesError && (
            <span className="text-xs text-red-400 bg-red-900/40 px-2 py-1 rounded-full">
              ⚠ Features unavailable
            </span>
          )}
          {isLoading && (
            <span className="text-xs text-blue-400 bg-blue-900/40 px-2 py-1 rounded-full flex items-center gap-1">
              <span className="w-3 h-3 border border-blue-400 border-t-transparent rounded-full animate-spin inline-block" />
              Loading data…
            </span>
          )}
          {!isLoading && !isLocationsError && (
            <span className="text-xs text-green-400 bg-green-900/40 px-2 py-1 rounded-full">
              ✓ {locationCount} locations
            </span>
          )}

          {/* Auth section */}
          {user ? (
            <div className="flex items-center gap-2 border-l border-slate-700 pl-2 ml-1">
              <Link
                to={profile?.username ? `/profile/${profile.username}` : '/map'}
                className="flex items-center gap-1.5 text-xs text-slate-300 hover:text-white transition-colors"
              >
                <Avatar
                  username={profile?.username ?? user.email ?? 'user'}
                  displayName={profile?.display_name}
                  size="sm"
                />
                <span>{profile?.username ?? user.email}</span>
              </Link>
              <button
                onClick={() => signOut()}
                className="text-xs text-slate-400 hover:text-white hover:bg-slate-700/60 px-2 py-1 rounded-lg transition-colors"
              >
                Log out
              </button>
            </div>
          ) : (
            <div className="border-l border-slate-700 pl-2 ml-1">
              <button
                onClick={() => navigate('/login')}
                className="text-xs text-slate-300 hover:text-white hover:bg-slate-700/60 px-3 py-1 rounded-lg transition-colors"
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
