import { useState } from 'react';
import type { LayerState } from '../types';
import { useAuth } from '../contexts/AuthContext';

interface LayerControlsProps {
  layers: LayerState;
  onChange: (layers: LayerState) => void;
}

const LAND_ACCESS_LEGEND = [
  { color: '#22c55e', label: 'OK to Detect' },
  { color: '#eab308', label: 'Permit Required' },
  { color: '#ef4444', label: 'Off Limits' },
  { color: '#f97316', label: 'Verify First' },
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
      { key: 'cemetery',     label: 'Cemetery',        color: '#6366f1' },
      { key: 'mission',      label: 'Mission',         color: '#d97706' },
      { key: 'school',       label: 'School',          color: '#8b5cf6' },
      { key: 'fairground',   label: 'Fairground',      color: '#eab308' },
      { key: 'abandoned_fairground', label: 'Abandoned Fairground', color: '#d97706' },
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
      { key: 'heatmap',      label: 'Activity Heatmap',   color: '#f97316' },
      { key: 'blm',          label: 'Land Access',         color: '#22c55e' },
      { key: 'aerials_1955', label: '1955 Historical Aerials', color: '#78716c' },
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
        className="flex items-center gap-1.5 bg-stone-900 backdrop-blur-sm border border-stone-700 shadow-lg rounded-xl px-3 py-2 text-xs font-medium text-stone-100 hover:bg-stone-800 transition-colors"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
        Layers
      </button>
    );
  }

  return (
    <div className="bg-stone-900 border border-stone-700 rounded-xl shadow-xl p-3 w-72 max-h-[80vh] overflow-y-auto scrollbar-thin scrollbar-thumb-stone-700 scrollbar-track-transparent">
      <div className="flex items-center justify-between mb-3 px-1">
        <h2 className="text-xs font-semibold tracking-widest uppercase text-stone-100">
          Map Layers
        </h2>
        <button
          onClick={() => setPanelOpen(false)}
          className="text-stone-100 hover:text-white transition-colors"
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

          return (
            <div key={section.title} className="rounded-lg overflow-hidden">
              {/* Section header */}
              <div className="flex items-center justify-between px-2 py-1.5 bg-stone-800">
                <button
                  onClick={() => toggleSection(section.items)}
                  className="text-[10px] font-semibold tracking-wider uppercase text-stone-300 hover:text-stone-100 transition-colors"
                  title={allOn ? 'Turn all off' : 'Turn all on'}
                >
                  {section.title}
                </button>
                <button
                  onClick={() => toggleCollapse(section.title)}
                  className="text-stone-400 hover:text-stone-200 transition-colors"
                  aria-label={isCollapsed ? 'Expand section' : 'Collapse section'}
                >
                  <svg
                    className={`w-3.5 h-3.5 transition-transform duration-200 ${isCollapsed ? '-rotate-90' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
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
                              ? 'bg-stone-800 text-stone-100'
                              : 'bg-transparent text-stone-400 hover:bg-stone-800/60'
                            }`}
                        >
                          {/* Color swatch */}
                          <span
                            className="inline-block w-3 h-3 rounded-sm flex-shrink-0 transition-opacity duration-150"
                            style={{ backgroundColor: color, opacity: active ? 1 : 0.7 }}
                          />

                          {/* Label */}
                          <span className="text-xs font-medium leading-tight flex-1">{label}</span>

                          {/* Toggle pill */}
                          <span
                            className={`relative inline-flex h-4 w-8 flex-shrink-0 rounded-full transition-colors duration-200
                              ${active ? 'bg-amber-600' : 'bg-stone-700'}`}
                          >
                            <span
                              className={`inline-block h-3 w-3 mt-0.5 rounded-full bg-white shadow transition-transform duration-200
                                ${active ? 'translate-x-4' : 'translate-x-0.5'}`}
                            />
                          </span>
                        </button>

                        {/* Land Access legend — shown when blm is active */}
                        {key === 'blm' && active && (
                          <div className="mt-2 mx-1 rounded-lg overflow-hidden border border-stone-700 bg-stone-800 shadow-sm">
                            {/* Legend header */}
                            <div className="px-3 py-1.5 border-b border-stone-700">
                              <p className="text-[10px] font-semibold tracking-widest uppercase text-stone-400">Access Key</p>
                            </div>
                            {/* Legend rows */}
                            <div className="divide-y divide-stone-700">
                              {LAND_ACCESS_LEGEND.map(({ color: c, label: l }) => (
                                <div key={l} className="flex items-center gap-2.5 px-3 py-1.5">
                                  <span
                                    className="flex-shrink-0 w-3 h-3 rounded-sm shadow-sm"
                                    style={{ backgroundColor: c }}
                                  />
                                  <span className="text-xs text-stone-300 leading-tight">{l}</span>
                                </div>
                              ))}
                            </div>
                            {/* Footer hint */}
                            <div className="px-3 py-1.5 border-t border-stone-700">
                              <p className="text-[10px] text-stone-500 flex items-center gap-1">
                                <svg className="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                </svg>
                                Zoom to level 9+ to load
                              </p>
                            </div>
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
            <div className="h-px flex-1 bg-stone-700" />
            <span className="text-xs text-stone-500 uppercase tracking-wider">Personal</span>
            <div className="h-px flex-1 bg-stone-700" />
          </div>

          <div className="rounded-lg overflow-hidden">
            <ul className="px-2 py-1 space-y-0.5">
              <li>
                <button
                  onClick={() => toggle('my_hunts')}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all duration-150 text-left
                    ${layers.my_hunts
                      ? 'bg-stone-800 text-stone-100'
                      : 'bg-transparent text-stone-400 hover:bg-stone-800/60'
                    }`}
                >
                  <span
                    className="inline-block w-3 h-3 rounded-sm flex-shrink-0 transition-opacity duration-150"
                    style={{ backgroundColor: '#10b981', opacity: layers.my_hunts ? 1 : 0.7 }}
                  />
                  <span className="text-xs font-medium leading-tight flex-1">My Hunts</span>
                  <span
                    className={`relative inline-flex h-4 w-8 flex-shrink-0 rounded-full transition-colors duration-200
                      ${layers.my_hunts ? 'bg-emerald-600' : 'bg-stone-700'}`}
                  >
                    <span
                      className={`inline-block h-3 w-3 mt-0.5 rounded-full bg-white shadow transition-transform duration-200
                        ${layers.my_hunts ? 'translate-x-4' : 'translate-x-0.5'}`}
                    />
                  </span>
                </button>
              </li>
              <li>
                <button
                  onClick={() => toggle('group_events')}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md transition-all duration-150 text-left
                    ${layers.group_events
                      ? 'bg-stone-800 text-stone-100'
                      : 'bg-transparent text-stone-400 hover:bg-stone-800/60'
                    }`}
                >
                  <span
                    className="inline-block w-3 h-3 rounded-sm flex-shrink-0 transition-opacity duration-150"
                    style={{ backgroundColor: '#8b5cf6', opacity: layers.group_events ? 1 : 0.7 }}
                  />
                  <span className="text-xs font-medium leading-tight flex-1">Group Events</span>
                  <span
                    className={`relative inline-flex h-4 w-8 flex-shrink-0 rounded-full transition-colors duration-200
                      ${layers.group_events ? 'bg-violet-500' : 'bg-stone-700'}`}
                  >
                    <span
                      className={`inline-block h-3 w-3 mt-0.5 rounded-full bg-white shadow transition-transform duration-200
                        ${layers.group_events ? 'translate-x-4' : 'translate-x-0.5'}`}
                    />
                  </span>
                </button>
              </li>
            </ul>
          </div>
        </>
      )}

      <p className="mt-3 text-xs text-stone-500 text-center">Click map to score a location</p>
      {user && (
        <p className="mt-1 text-xs text-stone-500 text-center">Right-click to log a hunt</p>
      )}
    </div>
  );
}
