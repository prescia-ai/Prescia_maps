import type { LayerState } from '../types';

interface LayerControlsProps {
  layers: LayerState;
  onChange: (layers: LayerState) => void;
}

interface LayerDef {
  key: keyof LayerState;
  label: string;
  color: string;
  icon: string;
}

const LAYER_DEFS: LayerDef[] = [
  { key: 'events',    label: 'Historical Events', color: 'bg-blue-500',   icon: '📍' },
  { key: 'railroads', label: 'Railroads',          color: 'bg-red-500',    icon: '🚂' },
  { key: 'trails',    label: 'Trails & Routes',    color: 'bg-green-500',  icon: '🥾' },
  { key: 'mines',     label: 'Mines & Camps',      color: 'bg-yellow-500', icon: '⛏️' },
  { key: 'heatmap',   label: 'Activity Heatmap',   color: 'bg-orange-500', icon: '🌡️' },
  { key: 'blm',       label: 'BLM Public Lands',   color: 'bg-yellow-600', icon: '🏔️' },
];

export default function LayerControls({ layers, onChange }: LayerControlsProps) {
  const toggle = (key: keyof LayerState) => {
    onChange({ ...layers, [key]: !layers[key] });
  };

  return (
    <div className="bg-slate-900/90 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl p-4 w-56">
      <h2 className="text-xs font-semibold tracking-widest uppercase text-slate-400 mb-3 flex items-center gap-2">
        <span>🗺️</span> Map Layers
      </h2>

      <ul className="space-y-2">
        {LAYER_DEFS.map(({ key, label, color, icon }) => {
          const active = layers[key];
          return (
            <li key={key}>
              <button
                onClick={() => toggle(key)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150
                  ${active
                    ? 'bg-slate-700/80 text-white'
                    : 'bg-transparent text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                  }`}
              >
                {/* Toggle pill */}
                <span
                  className={`relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200
                    ${active ? color : 'bg-slate-600'}`}
                >
                  <span
                    className={`inline-block h-4 w-4 mt-0.5 rounded-full bg-white shadow transition-transform duration-200
                      ${active ? 'translate-x-4' : 'translate-x-0.5'}`}
                  />
                </span>

                <span className="text-base leading-none">{icon}</span>
                <span className="text-sm font-medium leading-tight">{label}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 text-xs text-slate-500 text-center">Click map to score a location</p>
    </div>
  );
}
