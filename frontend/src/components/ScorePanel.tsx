import LoadingSpinner from './LoadingSpinner';
import type { ScoreResponse } from '../types';

interface ScorePanelProps {
  lat: number;
  lon: number;
  score: ScoreResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  onClose: () => void;
}

function scoreColor(score: number): string {
  if (score >= 75) return 'text-green-400';
  if (score >= 50) return 'text-yellow-400';
  if (score >= 25) return 'text-orange-400';
  return 'text-red-400';
}

function scoreBg(score: number): string {
  if (score >= 75) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  if (score >= 25) return 'bg-orange-500';
  return 'bg-red-500';
}

function scoreLabel(score: number): string {
  if (score >= 80) return 'Exceptional';
  if (score >= 60) return 'Excellent';
  if (score >= 40) return 'Good';
  if (score >= 20) return 'Fair';
  return 'Poor';
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

function GaugeArc({ score }: { score: number }) {
  // SVG semi-circle gauge
  const pct = Math.min(100, Math.max(0, score)) / 100;
  const circumference = Math.PI * 54; // r=54, half-circle
  const offset = circumference * (1 - pct);
  const color =
    score >= 75 ? '#22c55e' :
    score >= 50 ? '#eab308' :
    score >= 25 ? '#f97316' :
    '#ef4444';

  return (
    <svg viewBox="0 0 120 70" className="w-36 h-24 mx-auto">
      {/* Track */}
      <path
        d="M 10 65 A 54 54 0 0 1 110 65"
        fill="none"
        stroke="#e7e5e4"
        strokeWidth="10"
        strokeLinecap="round"
      />
      {/* Value arc */}
      <path
        d="M 10 65 A 54 54 0 0 1 110 65"
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${circumference}`}
        strokeDashoffset={`${offset}`}
        style={{ transition: 'stroke-dashoffset 0.8s ease' }}
      />
      {/* Score text */}
      <text
        x="60"
        y="62"
        textAnchor="middle"
        fontSize="22"
        fontWeight="bold"
        fill={color}
      >
        {Math.round(score)}
      </text>
    </svg>
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
          <h3 className="text-sm font-semibold text-stone-900">Location Score</h3>
          <p className="text-xs text-stone-400 font-mono mt-0.5">
            {lat.toFixed(4)}, {lon.toFixed(4)}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-stone-400 hover:text-stone-700 transition-colors"
          aria-label="Close score panel"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="p-4">
        {isLoading && <LoadingSpinner message="Calculating score…" />}

        {isError && (
          <p className="text-sm text-red-500 text-center py-4">
            Failed to load score. Is the backend running?
          </p>
        )}

        {score && !isLoading && (
          <>
            {/* Gauge */}
            <GaugeArc score={score.score} />

            <div className="text-center -mt-1 mb-3">
              <span className={`text-lg font-bold ${scoreColor(score.score)}`}>
                {scoreLabel(score.score)}
              </span>
              <span className="text-stone-400 text-sm ml-2">detecting potential</span>
            </div>

            <div className="text-center mb-3">
              <span className="text-xs text-stone-500 bg-stone-50 px-2 py-1 rounded-full">
                {score.nearby_count} historical site{score.nearby_count !== 1 ? 's' : ''} within 10 km
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

            {/* Breakdown — only show meaningful entries */}
            {(() => {
              const SKIP_KEYS = new Set(['final_score', 'overlap_multiplier']);
              const entries = Object.entries(score.breakdown).filter(
                ([k, v]) => !SKIP_KEYS.has(k) && !k.startsWith('semantic:') && !k.startsWith('loc:') && v > 0
              );
              if (!entries.length) return null;

              // Separate bonuses from type/site score contributions
              const BONUS_KEYS = new Set(['near_water', 'near_route', 'near_intersection', 'near_cluster']);
              const bars = entries.filter(([k]) => !BONUS_KEYS.has(k));
              const bonuses = entries.filter(([k]) => BONUS_KEYS.has(k));
              const maxVal = Math.max(...bars.map(([, v]) => v), 1);

              return (
                <div className="space-y-2">
                  <p className="text-xs font-semibold tracking-widest uppercase text-stone-400">
                    Why this spot?
                  </p>
                  {bars.map(([key, val]) => {
                    const barPct = Math.min(100, (val / maxVal) * 100);
                    return (
                      <div key={key}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-stone-600 truncate max-w-[180px]" title={key}>{key}</span>
                          <span className="text-stone-400 ml-1 shrink-0">{val.toFixed(1)}</span>
                        </div>
                        <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${scoreBg(score.score)}`}
                            style={{ width: `${barPct}%`, transition: 'width 0.6s ease' }}
                          />
                        </div>
                      </div>
                    );
                  })}

                  {/* Bonuses */}
                  {bonuses.map(([key, val]) => (
                    <div key={key} className="flex items-center justify-between text-xs text-stone-500">
                      <span>
                        {key === 'near_water' && '💧 Near water source'}
                        {key === 'near_route' && '🛤 Near historic route'}
                        {key === 'near_intersection' && '✕ Route intersection'}
                        {key === 'near_cluster' && '📍 Multiple overlapping sites'}
                      </span>
                      <span className="text-green-600 font-medium">+{val.toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              );
            })()}
          </>
        )}
      </div>
    </div>
  );
}
