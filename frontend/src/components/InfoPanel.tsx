import type { LocationFeature, LocationType } from '../types';

interface InfoPanelProps {
  feature: LocationFeature;
  onClose: () => void;
}

const TYPE_CONFIG: Record<string, { bg: string; text: string; label: string }> = {
  battle:         { bg: 'bg-red-100',    text: 'text-red-700',    label: 'Battle' },
  town:           { bg: 'bg-blue-100',   text: 'text-blue-700',   label: 'Town' },
  mine:           { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Mine' },
  camp:           { bg: 'bg-green-100',  text: 'text-green-700',  label: 'Camp' },
  railroad_stop:  { bg: 'bg-purple-100', text: 'text-purple-700', label: 'Railroad Stop' },
  trail:          { bg: 'bg-teal-100',   text: 'text-teal-700',   label: 'Trail' },
};

function getTypeConfig(type: LocationType) {
  return TYPE_CONFIG[type] ?? { bg: 'bg-stone-100', text: 'text-stone-600', label: type };
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const color =
    pct >= 75 ? 'bg-green-500' :
    pct >= 50 ? 'bg-yellow-500' :
    'bg-red-500';

  return (
    <div>
      <div className="flex justify-between text-xs text-stone-500 mb-1">
        <span>Confidence</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
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
    <div className="bg-white/95 backdrop-blur-sm border border-stone-200 rounded-xl shadow-lg w-72 overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between p-4 pb-3 border-b border-stone-100">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-stone-900 text-sm leading-tight truncate pr-2">{name}</h3>
          {year != null && (
            <p className="text-xs text-stone-500 mt-0.5">
              {typeof year === 'number' ? `c. ${year}` : year}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-stone-400 hover:text-stone-700 transition-colors flex-shrink-0 -mt-0.5 -mr-0.5"
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
          <p className="text-sm text-stone-600 leading-relaxed">{description}</p>
        )}

        {/* Source */}
        {source && (
          <div className="text-xs text-stone-400">
            <span className="text-stone-500 font-medium">Source:</span> {source}
          </div>
        )}

        {/* Confidence */}
        {confidence != null && <ConfidenceBar value={confidence} />}
      </div>
    </div>
  );
}
