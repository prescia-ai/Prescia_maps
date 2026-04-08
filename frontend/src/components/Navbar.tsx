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
        </div>
      </div>
    </div>
  );
}
