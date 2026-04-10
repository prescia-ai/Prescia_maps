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
  if (score >= 75) return 'Excellent';
  if (score >= 50) return 'Good';
  if (score >= 25) return 'Fair';
  return 'Poor';
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

            <div className="text-center -mt-1 mb-4">
              <span className={`text-lg font-bold ${scoreColor(score.score)}`}>
                {scoreLabel(score.score)}
              </span>
              <span className="text-stone-400 text-sm ml-2">detecting potential</span>
            </div>

            {/* Breakdown */}
            {Object.keys(score.breakdown).length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold tracking-widest uppercase text-stone-400">
                  Score Breakdown
                </p>
                {Object.entries(score.breakdown).map(([key, val]) => {
                  const pct = Math.min(100, Math.max(0, val));
                  return (
                    <div key={key}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-stone-600 capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className="text-stone-400">{pct.toFixed(1)}</span>
                      </div>
                      <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${scoreBg(pct)}`}
                          style={{ width: `${pct}%`, transition: 'width 0.6s ease' }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
