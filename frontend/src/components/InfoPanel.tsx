import type { LocationFeature, LocationType } from '../types';

interface InfoPanelProps {
  feature: LocationFeature;
  onClose: () => void;
}

const TYPE_CONFIG: Record<string, { bg: string; text: string; label: string }> = {
  battle:         { bg: 'bg-red-900/60',    text: 'text-red-300',    label: 'Battle' },
  town:           { bg: 'bg-blue-900/60',   text: 'text-blue-300',   label: 'Town' },
  mine:           { bg: 'bg-yellow-900/60', text: 'text-yellow-300', label: 'Mine' },
  camp:           { bg: 'bg-green-900/60',  text: 'text-green-300',  label: 'Camp' },
  railroad_stop:  { bg: 'bg-purple-900/60', text: 'text-purple-300', label: 'Railroad Stop' },
  trail:          { bg: 'bg-teal-900/60',   text: 'text-teal-300',   label: 'Trail' },
};

function getTypeConfig(type: LocationType) {
  return TYPE_CONFIG[type] ?? { bg: 'bg-slate-700/60', text: 'text-slate-300', label: type };
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const color =
    pct >= 75 ? 'bg-green-500' :
    pct >= 50 ? 'bg-yellow-500' :
    'bg-red-500';

  return (
    <div>
      <div className="flex justify-between text-xs text-slate-400 mb-1">
        <span>Confidence</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function InfoPanel({ feature, onClose }: InfoPanelProps) {
  const { name, type, year, description, source, confidence } = feature.properties;
  const cfg = getTypeConfig(type);

  return (
    <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl w-72 overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between p-4 pb-3 border-b border-slate-700/50">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white text-sm leading-tight truncate pr-2">{name}</h3>
          {year != null && (
            <p className="text-xs text-slate-400 mt-0.5">
              {typeof year === 'number' ? `c. ${year}` : year}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-white transition-colors flex-shrink-0 -mt-0.5 -mr-0.5"
          aria-label="Close"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3 custom-scrollbar overflow-y-auto max-h-64">
        {/* Type badge */}
        <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.text}`}>
          {cfg.label}
        </span>

        {/* Description */}
        {description && (
          <p className="text-sm text-slate-300 leading-relaxed">{description}</p>
        )}

        {/* Source */}
        {source && (
          <div className="text-xs text-slate-500">
            <span className="text-slate-400 font-medium">Source:</span> {source}
          </div>
        )}

        {/* Confidence */}
        {confidence != null && <ConfidenceBar value={confidence} />}
      </div>
    </div>
  );
}
