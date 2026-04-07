import { useState, useCallback } from 'react';
import MapView from './components/MapView';
import LayerControls from './components/LayerControls';
import InfoPanel from './components/InfoPanel';
import ScorePanel from './components/ScorePanel';
import LoadingSpinner from './components/LoadingSpinner';
import { useLocations } from './hooks/useLocations';
import { useFeatures } from './hooks/useFeatures';
import { useHeatmap } from './hooks/useHeatmap';
import { useScore } from './hooks/useScore';
import type { LocationFeature, LayerState } from './types';

const DEFAULT_LAYERS: LayerState = {
  events:    true,
  railroads: true,
  trails:    true,
  mines:     true,
  heatmap:   false,
  blm:       false,
};

export default function App() {
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);
  const [selectedFeature, setSelectedFeature] = useState<LocationFeature | null>(null);
  const [clickedCoords, setClickedCoords] = useState<{ lat: number; lon: number } | null>(null);

  const locationsQuery = useLocations();
  const featuresQuery  = useFeatures();
  const heatmapQuery   = useHeatmap();
  const scoreQuery     = useScore(clickedCoords?.lat ?? null, clickedCoords?.lon ?? null);

  const handleMapClick = useCallback((lat: number, lon: number) => {
    setSelectedFeature(null);
    setClickedCoords({ lat, lon });
  }, []);

  const handleLocationSelect = useCallback((f: LocationFeature) => {
    setSelectedFeature(f);
    setClickedCoords(null);
  }, []);

  const handleCloseInfo  = useCallback(() => setSelectedFeature(null), []);
  const handleCloseScore = useCallback(() => setClickedCoords(null), []);

  const locations      = locationsQuery.data?.features ?? [];
  const linearFeatures = featuresQuery.data?.features  ?? [];
  const heatmapPoints  = heatmapQuery.data             ?? [];

  const isInitialLoading =
    locationsQuery.isLoading || featuresQuery.isLoading || heatmapQuery.isLoading;

  return (
    <div className="relative w-screen h-screen bg-slate-950 overflow-hidden">
      {/* Full-screen map */}
      <div className="absolute inset-0">
        <MapView
          locations={locations}
          linearFeatures={linearFeatures}
          heatmapPoints={heatmapPoints}
          layers={layers}
          onMapClick={handleMapClick}
          onLocationSelect={handleLocationSelect}
        />
      </div>

      {/* Top bar / branding */}
      <div className="absolute top-0 left-0 right-0 z-10 pointer-events-none">
        <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-b from-slate-950/90 to-transparent">
          <span className="text-2xl">🗺️</span>
          <div>
            <h1 className="text-white font-bold text-sm leading-tight tracking-wide">
              Prescia Maps
            </h1>
            <p className="text-slate-400 text-xs leading-tight">
              Historical Activity &amp; Metal Detecting Intelligence
            </p>
          </div>

          {/* Data status badges */}
          <div className="ml-auto flex items-center gap-2 pointer-events-auto">
            {locationsQuery.isError && (
              <span className="text-xs text-red-400 bg-red-900/40 px-2 py-1 rounded-full">
                ⚠ Locations unavailable
              </span>
            )}
            {featuresQuery.isError && (
              <span className="text-xs text-red-400 bg-red-900/40 px-2 py-1 rounded-full">
                ⚠ Features unavailable
              </span>
            )}
            {isInitialLoading && (
              <span className="text-xs text-blue-400 bg-blue-900/40 px-2 py-1 rounded-full flex items-center gap-1">
                <span className="w-3 h-3 border border-blue-400 border-t-transparent rounded-full animate-spin inline-block" />
                Loading data…
              </span>
            )}
            {!isInitialLoading && !locationsQuery.isError && (
              <span className="text-xs text-green-400 bg-green-900/40 px-2 py-1 rounded-full">
                ✓ {locations.length} locations
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Left panel: layer controls */}
      <div className="absolute top-16 left-4 z-10">
        <LayerControls layers={layers} onChange={setLayers} />
      </div>

      {/* Bottom-right: info / score panels (offset left of legend) */}
      <div className="absolute bottom-6 right-48 z-10 flex flex-col gap-3 items-end">
        {selectedFeature && (
          <InfoPanel feature={selectedFeature} onClose={handleCloseInfo} />
        )}

        {clickedCoords && (
          <ScorePanel
            lat={clickedCoords.lat}
            lon={clickedCoords.lon}
            score={scoreQuery.data}
            isLoading={scoreQuery.isLoading}
            isError={scoreQuery.isError}
            onClose={handleCloseScore}
          />
        )}
      </div>

      {/* Full-screen loading overlay (first paint only) */}
      {isInitialLoading && !locationsQuery.data && !featuresQuery.data && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl px-10 py-8 shadow-2xl">
            <LoadingSpinner message="Loading map data…" />
            <p className="text-xs text-slate-500 text-center mt-1">Connecting to backend API</p>
          </div>
        </div>
      )}

      {/* Legend – bottom-right, always visible */}
      <div className="absolute bottom-6 right-4 z-10">
        <div className="bg-slate-900/80 backdrop-blur-sm border border-slate-700 rounded-xl p-3 text-xs text-slate-300">
          <p className="font-semibold text-slate-400 uppercase tracking-widest mb-2 text-[10px]">Legend</p>
          <div className="space-y-1">
            {[
              { color: '#ef4444', label: 'Battle' },
              { color: '#3b82f6', label: 'Town / Ghost Town' },
              { color: '#f59e0b', label: 'Mine' },
              { color: '#22c55e', label: 'Camp' },
              { color: '#a855f7', label: 'Railroad Stop' },
              { color: '#14b8a6', label: 'Trail Point' },
              { color: '#f97316', label: 'Fort / Structure' },
              { color: '#84cc16', label: 'Stagecoach Stop' },
              { color: '#ec4899', label: 'Mission / Church' },
              { color: '#06b6d4', label: 'Ferry Crossing' },
              { color: '#6366f1', label: 'Cemetery' },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-2">
                <span
                  className="inline-block w-3 h-3 rounded-full flex-shrink-0 border border-white/20"
                  style={{ backgroundColor: color }}
                />
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
