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

          <button
            onClick={onImportClick}
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
                d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5-5m0 0l5 5m-5-5v12"
              />
            </svg>
            Import Data
          </button>

          {user && (
            <Link
              to="/submit"
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
                to={profile?.username ? `/profile/${profile.username}` : '/map'}
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
              <button
                onClick={() => signOut()}
                className="text-xs text-stone-500 hover:text-stone-800 hover:bg-stone-100 px-2 py-1 rounded-lg transition-colors"
              >
                Log out
              </button>
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
