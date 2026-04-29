import { useState } from 'react';
import type { LayerState } from '../types';
import { useAuth } from '../contexts/AuthContext';

interface LayerControlsProps {
  layers: LayerState;
  onChange: (layers: LayerState) => void;
}

const LAND_ACCESS_LEGEND = [
  { color: '#22c55e', label: 'Public — OK to Detect' },
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

// Grouped route definitions — each group has a master toggle that controls
// all of its child sub-layers (linear feature + stop points) together.
interface GroupRouteDef {
  groupedKey: keyof LayerState;
  label: string;
  accentColor: string;
  items: TypeDef[];
}

const ROUTE_GROUPS: GroupRouteDef[] = [
  {
    groupedKey: 'grouped_trails',
    label: 'Historic Trails & Landmarks',
    accentColor: '#22c55e',
    items: [
      { key: 'trail',          label: 'Trail Routes (linear)', color: '#22c55e' },
      { key: 'trail_landmark', label: 'Trail Landmarks',       color: '#84cc16' },
    ],
  },
  {
    groupedKey: 'grouped_stagecoach',
    label: 'Stagecoach Routes & Stops',
    accentColor: '#d97706',
    items: [
      { key: 'road',           label: 'Stagecoach Routes (linear)', color: '#d97706' },
      { key: 'stagecoach_stop', label: 'Stagecoach Stops',          color: '#84cc16' },
    ],
  },
  {
    groupedKey: 'grouped_railroads',
    label: 'Railroad Lines & Stops',
    accentColor: '#ef4444',
    items: [
      { key: 'railroad',      label: 'Railroad Lines (linear)', color: '#ef4444' },
      { key: 'railroad_stop', label: 'Railroad Stops',          color: '#a855f7' },
    ],
  },
  {
    groupedKey: 'grouped_pony_express',
    label: 'Pony Express',
    accentColor: '#dc2626',
    items: [
      { key: 'pony_express', label: 'Pony Express Stations', color: '#dc2626' },
    ],
  },
];

const SECTIONS: SectionDef[] = [
  {
    title: 'Battles & Events',
    items: [
      { key: 'battle',       label: 'Battle',         color: '#ef4444' },
      { key: 'structure',    label: 'Fort / Structure', color: '#f97316' },
      { key: 'abandoned_fairground', label: 'Abandoned Fairground', color: '#d97706' },
      { key: 'trading_post',    label: 'Trading Post',     color: '#b45309' },
      { key: 'abandoned_church', label: 'Abandoned Church', color: '#7c3aed' },
      { key: 'historic_brothel', label: 'Historic Brothel', color: '#f43f5e' },
    ],
  },
  {
    title: 'Mining & Resources',
    items: [
      { key: 'mine',   label: 'Mine',   color: '#f59e0b' },
      { key: 'camp',   label: 'Camp',   color: '#22c55e' },
    ],
  },
  {
    title: 'Other',
    items: [
      { key: 'town',      label: 'Town / Ghost Town', color: '#3b82f6' },
      { key: 'locale',    label: 'Historic Locale',   color: '#94a3b8' },
    ],
  },
  {
    title: 'Overlays',
    items: [
      { key: 'heatmap',      label: 'Activity Heatmap',   color: '#f97316' },
      { key: 'blm',          label: 'Public Land (BLM/USFS)',  color: '#22c55e' },
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

  // Toggle a route group: flips the master key and all child sub-layer keys together.
  const handleGroupedToggle = (group: GroupRouteDef) => {
    const subKeys = group.items.map((i) => i.key);
    const allOn = subKeys.every((k) => layers[k]);
    const newState = !allOn;
    const update: Partial<LayerState> = { [group.groupedKey]: newState };
    subKeys.forEach((k) => { update[k] = newState; });
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
        {/* ── Routes & Stops (grouped) ─────────────────────────────────── */}
        <div className="rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-2 py-1.5 bg-stone-800">
            <span className="text-[10px] font-semibold tracking-wider uppercase text-stone-300">
              Routes &amp; Stops
            </span>
            <button
              onClick={() => toggleCollapse('Routes & Stops')}
              className="text-stone-400 hover:text-stone-200 transition-colors"
              aria-label={collapsed['Routes & Stops'] ? 'Expand section' : 'Collapse section'}
            >
              <svg
                className={`w-3.5 h-3.5 transition-transform duration-200 ${collapsed['Routes & Stops'] ? '-rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>

          {!collapsed['Routes & Stops'] && (
            <ul className="px-2 py-1 space-y-1">
              {ROUTE_GROUPS.map((group) => {
                const subKeys = group.items.map((i) => i.key);
                const allSubOn = subKeys.every((k) => layers[k]);
                const someSubOn = subKeys.some((k) => layers[k]);
                const isGroupCollapsed = !!collapsed[group.groupedKey as string];

                return (
                  <li key={group.groupedKey as string}>
                    {/* Master group toggle row */}
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleGroupedToggle(group)}
                        className={`flex-1 flex items-center gap-2 px-2 py-1.5 rounded-md transition-all duration-150 text-left
                          ${allSubOn
                            ? 'bg-stone-800 text-stone-100'
                            : 'bg-transparent text-stone-400 hover:bg-stone-800/60'
                          }`}
                      >
                        {/* Color swatch — half-filled when mixed state */}
                        <span
                          className="inline-block w-3 h-3 rounded-sm flex-shrink-0 transition-opacity duration-150"
                          style={{
                            backgroundColor: group.accentColor,
                            opacity: allSubOn ? 1 : someSubOn ? 0.5 : 0.3,
                          }}
                        />
                        <span className="text-xs font-semibold leading-tight flex-1">{group.label}</span>
                        {/* Toggle pill */}
                        <span
                          className={`relative inline-flex h-4 w-8 flex-shrink-0 rounded-full transition-colors duration-200
                            ${allSubOn ? 'bg-amber-600' : someSubOn ? 'bg-amber-900' : 'bg-stone-700'}`}
                        >
                          <span
                            className={`inline-block h-3 w-3 mt-0.5 rounded-full bg-white shadow transition-transform duration-200
                              ${allSubOn ? 'translate-x-4' : 'translate-x-0.5'}`}
                          />
                        </span>
                      </button>
                      {/* Collapse sub-items chevron */}
                      {group.items.length > 1 && (
                        <button
                          onClick={() => toggleCollapse(group.groupedKey as string)}
                          className="text-stone-500 hover:text-stone-300 transition-colors px-1"
                          aria-label={isGroupCollapsed ? 'Show sub-layers' : 'Hide sub-layers'}
                        >
                          <svg
                            className={`w-3 h-3 transition-transform duration-200 ${isGroupCollapsed ? '-rotate-90' : ''}`}
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                      )}
                    </div>

                    {/* Child sub-layer toggles */}
                    {!isGroupCollapsed && group.items.length > 1 && (
                      <ul className="ml-4 mt-0.5 space-y-0.5 border-l border-stone-700 pl-2">
                        {group.items.map(({ key, label, color }) => {
                          const active = layers[key];
                          return (
                            <li key={key as string}>
                              <button
                                onClick={() => toggle(key)}
                                className={`w-full flex items-center gap-2 px-2 py-1 rounded-md transition-all duration-150 text-left
                                  ${active
                                    ? 'bg-stone-800 text-stone-100'
                                    : 'bg-transparent text-stone-400 hover:bg-stone-800/60'
                                  }`}
                              >
                                <span
                                  className="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
                                  style={{ backgroundColor: color, opacity: active ? 1 : 0.5 }}
                                />
                                <span className="text-[11px] leading-tight flex-1">{label}</span>
                                <span
                                  className={`relative inline-flex h-3.5 w-7 flex-shrink-0 rounded-full transition-colors duration-200
                                    ${active ? 'bg-amber-600' : 'bg-stone-700'}`}
                                >
                                  <span
                                    className={`inline-block h-2.5 w-2.5 mt-0.5 rounded-full bg-white shadow transition-transform duration-200
                                      ${active ? 'translate-x-3.5' : 'translate-x-0.5'}`}
                                  />
                                </span>
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* ── Other sections ───────────────────────────────────────────── */}
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
                                Only public BLM/USFS land shown
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
