import LoadingSpinner from './LoadingSpinner';
import type { ScoreResponse, NearbyItem } from '../types';

interface ScorePanelProps {
  lat: number;
  lon: number;
  score: ScoreResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  onClose: () => void;
}

/** Land access badge colours and labels */
function accessibleBadge(accessible: string | null | undefined): { label: string; cls: string } | null {
  if (!accessible || accessible === 'unknown') return null;
  switch (accessible) {
    case 'allowed':
      return { label: '✓ Public land — detecting allowed', cls: 'bg-green-100 text-green-800 border-green-200' };
    case 'off_limits':
      return { label: '✗ Off-limits — detecting prohibited', cls: 'bg-red-100 text-red-800 border-red-200' };
    case 'private_permit':
      return { label: '⚠ Private land — permit required', cls: 'bg-amber-100 text-amber-800 border-amber-200' };
    case 'unsure':
      return { label: '? Verify access before detecting', cls: 'bg-stone-100 text-stone-700 border-stone-200' };
    default:
      return null;
  }
}

function NearbyList({ items }: { items: NearbyItem[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-3">
      <p className="text-xs font-semibold tracking-widest uppercase text-stone-400 mb-1.5">
        Nearby
      </p>
      <ul className="space-y-1">
        {items.map((item, idx) => (
          <li key={idx} className="flex items-start gap-1.5 text-xs text-stone-600">
            <span className="text-stone-400 mt-0.5 flex-shrink-0">•</span>
            <span className="truncate flex-1" title={item.name}>
              <span className="font-medium text-stone-700">
                {item.name || item.type}
              </span>
              {item.year ? <span className="text-stone-400"> ({item.year})</span> : null}
              <span className="text-stone-400"> — {item.distance_km.toFixed(1)} km</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ScorePanel({
  lat, lon, score, isLoading, isError, onClose,
}: ScorePanelProps) {
  return (
    <div className="bg-white/95 backdrop-blur-sm border border-stone-200 rounded-xl shadow-lg w-72 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-stone-100">
        <div>
          <h3 className="text-sm font-semibold text-stone-900">Site Insight</h3>
          <p className="text-xs text-stone-400 font-mono mt-0.5">
            {lat.toFixed(4)}, {lon.toFixed(4)}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-stone-400 hover:text-stone-700 transition-colors"
          aria-label="Close site insight panel"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="p-4">
        {isLoading && <LoadingSpinner message="Analyzing this location…" />}

        {isError && (
          <p className="text-sm text-red-500 text-center py-4">
            Failed to load site insight. Is the backend running?
          </p>
        )}

        {score && !isLoading && (
          <>
            {/* AI Summary */}
            <div className="bg-stone-50 border border-stone-100 rounded-lg px-3 py-2.5 mb-3">
              <p className="text-xs text-stone-500 flex items-center gap-1 mb-1 font-medium">
                <span>✨</span> AI Summary
              </p>
              <p className="text-xs text-stone-700 leading-relaxed">
                {score.summary ?? 'AI summary unavailable for this location.'}
              </p>
            </div>

            {/* Stats row */}
            <div className="flex items-center gap-2 flex-wrap mb-3">
              <span className="text-xs text-stone-500 bg-stone-50 px-2 py-1 rounded-full border border-stone-100">
                📍 {score.nearby_count} site{score.nearby_count !== 1 ? 's' : ''} within 10 km
              </span>
            </div>

            {/* Land access badge */}
            {(() => {
              const badge = accessibleBadge(score.accessible);
              if (!badge) return null;
              return (
                <div className={`mb-3 px-2 py-1.5 rounded-lg border text-xs font-medium text-center ${badge.cls}`}>
                  {badge.label}
                </div>
              );
            })()}

            {/* Nearby list */}
            <NearbyList items={score.nearby} />
          </>
        )}
      </div>
    </div>
  );
}
