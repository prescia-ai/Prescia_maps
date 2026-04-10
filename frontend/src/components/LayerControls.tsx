import { useState } from 'react';
import type { LayerState } from '../types';
import { useAuth } from '../contexts/AuthContext';

interface LayerControlsProps {
  layers: LayerState;
  onChange: (layers: LayerState) => void;
}

const LAND_ACCESS_LEGEND = [
  { color: '#22c55e', label: 'Public — OK to Detect' },
  { color: '#eab308', label: 'Private — Permit Required' },
  { color: '#ef4444', label: 'Off Limits' },
  { color: '#f97316', label: 'Unsure — Verify First' },
];

interface TypeDef {
  key: keyof LayerState;
  label: string;
  color: string;
}

interface SectionDef {
  title: string;
  items: TypeDef[];
}

const SECTIONS: SectionDef[] = [
  {
    title: 'Battles & Events',
    items: [
      { key: 'battle',       label: 'Battle',         color: '#ef4444' },
      { key: 'structure',    label: 'Fort / Structure', color: '#f97316' },
      { key: 'church',       label: 'Church',          color: '#ec4899' },
      { key: 'cemetery',     label: 'Cemetery',        color: '#6366f1' },
      { key: 'mission',      label: 'Mission',         color: '#d97706' },
      { key: 'school',       label: 'School',          color: '#8b5cf6' },
      { key: 'fairground',   label: 'Fairground',      color: '#eab308' },
      { key: 'trading_post',    label: 'Trading Post',     color: '#b45309' },
      { key: 'abandoned_church', label: 'Abandoned Church', color: '#ec4899' },
      { key: 'historic_brothel', label: 'Historic Brothel', color: '#f43f5e' },
    ],
  },
  {
    title: 'Trails & Routes',
    items: [
      { key: 'trail',          label: 'Trail',           color: '#14b8a6' },
      { key: 'stagecoach_stop', label: 'Stagecoach Stop', color: '#84cc16' },
      { key: 'ferry',          label: 'Ferry',           color: '#06b6d4' },
      { key: 'pony_express',   label: 'Pony Express',    color: '#dc2626' },
      { key: 'road',           label: 'Road (linear)',   color: '#d97706' },
    ],
  },
  {
    title: 'Railroads',
    items: [
      { key: 'railroad_stop', label: 'Railroad Stop',    color: '#a855f7' },
      { key: 'railroad',      label: 'Railroad (linear)', color: '#ef4444' },
    ],
  },
  {
    title: 'Mining & Resources',
    items: [
      { key: 'mine',   label: 'Mine',   color: '#f59e0b' },
      { key: 'camp',   label: 'Camp',   color: '#22c55e' },
      { key: 'spring', label: 'Spring', color: '#10b981' },
    ],
  },
  {
    title: 'Other',
    items: [
      { key: 'town',      label: 'Town / Ghost Town', color: '#3b82f6' },
      { key: 'locale',    label: 'Historic Locale',   color: '#94a3b8' },
      { key: 'shipwreck', label: 'Shipwreck',         color: '#0369a1' },
    ],
  },
  {
    title: 'Overlays',
    items: [
      { key: 'heatmap', label: 'Activity Heatmap', color: '#f97316' },
      { key: 'blm',     label: 'Land Access',      color: '#22c55e' },
    ],
  },
];

export default function LayerControls({ layers, onChange }: LayerControlsProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [panelOpen, setPanelOpen] = useState(false);
  const { user } = useAuth();

  const toggle = (key: keyof LayerState) => {
    onChange({ ...layers, [key]: !layers[key] });
  };

  const toggleSection = (items: TypeDef[]) => {
    const allOn = items.every((item) => layers[item.key]);
    const update: Partial<LayerState> = {};
    items.forEach((item) => {
      update[item.key] = !allOn as boolean;
    });
    onChange({ ...layers, ...update });
  };

  const toggleCollapse = (title: string) => {
    setCollapsed((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  if (!panelOpen) {
    return (
      <button
        onClick={() => setPanelOpen(true)}
        className="flex items-center gap-1.5 bg-white/95 backdrop-blur-sm border border-stone-200 shadow-lg rounded-xl px-3 py-2 text-xs font-medium text-stone-700 hover:bg-stone-50 hover:text-stone-900 transition-colors"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
        Layers
      </button>
    );
  }

  return (
    <div className="bg-white/95 backdrop-blur-sm border border-stone-200 rounded-xl shadow-lg p-3 w-64 max-h-[80vh] overflow-y-auto">
      <div className="flex items-center justify-between mb-3 px-1">
        <h2 className="text-xs font-semibold tracking-widest uppercase text-stone-500">
          Map Layers
        </h2>
        <button
          onClick={() => setPanelOpen(false)}
          className="text-stone-400 hover:text-stone-700 transition-colors"
          aria-label="Close layers panel"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="space-y-1.5">
        {SECTIONS.map((section) => {
          const isCollapsed = !!collapsed[section.title];
          const allOn = section.items.every((item) => layers[item.key]);
          const someOn = section.items.some((item) => layers[item.key]);

          return (
            <div key={section.title} className="border border-stone-200 rounded-lg overflow-hidden">
              {/* Section header */}
              <div className="flex items-center justify-between px-2 py-1.5 bg-stone-50">
                <button
                  onClick={() => toggleSection(section.items)}
                  className="flex items-center gap-1.5 text-xs font-semibold text-stone-600 hover:text-stone-900 transition-colors"
                  title={allOn ? 'Turn all off' : 'Turn all on'}
                >
                  <span
                    className={`inline-block w-2 h-2 rounded-full flex-shrink-0 transition-colors ${
                      allOn ? 'bg-amber-600' : someOn ? 'bg-stone-400' : 'bg-stone-200'
                    }`}
                  />
                  {section.title}
                </button>
                <button
                  onClick={() => toggleCollapse(section.title)}
                  className="text-stone-400 hover:text-stone-700 transition-colors text-xs px-1"
                  aria-label={isCollapsed ? 'Expand section' : 'Collapse section'}
                >
                  {isCollapsed ? '▶' : '▼'}
                </button>
              </div>

              {/* Section items */}
              {!isCollapsed && (
                <ul className="px-2 py-1 space-y-0.5">
                  {section.items.map(({ key, label, color }) => {
                    const active = layers[key];
                    return (
                      <li key={key}>
                        <button
                          onClick={() => toggle(key)}
                          className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all duration-150 text-left
                            ${active
                              ? 'bg-stone-100 text-stone-900'
                              : 'bg-transparent text-stone-500 hover:bg-stone-50 hover:text-stone-700'
                            }`}
                        >
                          {/* Color dot */}
                          <span
                            className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                            style={{ backgroundColor: active ? color : '#d1d5db' }}
                          />

                          {/* Label */}
                          <span className="text-xs font-medium leading-tight flex-1">{label}</span>

                          {/* Toggle pill */}
                          <span
                            className={`relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors duration-200
                              ${active ? 'bg-amber-600' : 'bg-stone-200'}`}
                          >
                            <span
                              className={`inline-block h-3 w-3 mt-0.5 rounded-full bg-white shadow transition-transform duration-200
                                ${active ? 'translate-x-3.5' : 'translate-x-0.5'}`}
                            />
                          </span>
                        </button>

                        {/* Land Access legend — shown when blm is active */}
                        {key === 'blm' && active && (
                          <div className="mt-1 ml-4 pl-2 border-l border-stone-200 space-y-0.5">
                            {LAND_ACCESS_LEGEND.map(({ color: c, label: l }) => (
                              <div key={l} className="flex items-center gap-2">
                                <span
                                  className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: c }}
                                />
                                <span className="text-xs text-stone-500">{l}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      {/* Personal layers — only when authenticated */}
      {user && (
        <>
          <div className="mt-3 mb-1 flex items-center gap-2 px-1">
            <div className="h-px flex-1 bg-stone-200" />
            <span className="text-xs text-stone-400 uppercase tracking-wider">Personal</span>
            <div className="h-px flex-1 bg-stone-200" />
          </div>

          <div className="border border-stone-200 rounded-lg overflow-hidden">
            <ul className="px-2 py-1 space-y-0.5">
              <li>
                <button
                  onClick={() => toggle('my_hunts')}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all duration-150 text-left
                    ${layers.my_hunts
                      ? 'bg-stone-100 text-stone-900'
                      : 'bg-transparent text-stone-500 hover:bg-stone-50 hover:text-stone-700'
                    }`}
                >
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: layers.my_hunts ? '#10b981' : '#d1d5db' }}
                  />
                  <span className="text-xs font-medium leading-tight flex-1">My Hunts</span>
                  <span
                    className={`relative inline-flex h-4 w-7 flex-shrink-0 rounded-full transition-colors duration-200
                      ${layers.my_hunts ? 'bg-emerald-600' : 'bg-stone-200'}`}
                  >
                    <span
                      className={`inline-block h-3 w-3 mt-0.5 rounded-full bg-white shadow transition-transform duration-200
                        ${layers.my_hunts ? 'translate-x-3.5' : 'translate-x-0.5'}`}
                    />
                  </span>
                </button>
              </li>
            </ul>
          </div>
        </>
      )}

      <p className="mt-3 text-xs text-stone-400 text-center">Click map to score a location</p>
      {user && (
        <p className="mt-1 text-xs text-stone-300 text-center">Right-click to log a hunt</p>
      )}
    </div>
  );
}
