import { useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import MapView from '../components/MapView';
import LayerControls from '../components/LayerControls';
import InfoPanel from '../components/InfoPanel';
import ScorePanel from '../components/ScorePanel';
import LandAccessPanel from '../components/LandAccessPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import Navbar from '../components/Navbar';
import ImportModal from '../components/ImportModal';
import { useLocations } from '../hooks/useLocations';
import { useFeatures } from '../hooks/useFeatures';
import { useHeatmap } from '../hooks/useHeatmap';
import { useScore } from '../hooks/useScore';
import { fetchLandAccess, putLandAccessOverride } from '../api/client';
import type { LocationFeature, LayerState, LandAccessResponse } from '../types';

const DEFAULT_LAYERS: LayerState = {
  battle:          true,
  town:            true,
  mine:            true,
  camp:            true,
  railroad_stop:   true,
  stagecoach_stop: true,
  trail:           true,
  structure:       true,
  church:          true,
  cemetery:        true,
  ferry:           true,
  fairground:      true,
  school:          true,
  spring:          true,
  locale:          true,
  mission:         true,
  trading_post:    true,
  shipwreck:        true,
  pony_express:     true,
  abandoned_church: true,
  historic_brothel: true,
  railroad:         true,
  road:            true,
  heatmap:         false,
  blm:             false,
};

export default function MapPage() {
  const queryClient = useQueryClient();
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);
  const [selectedFeature, setSelectedFeature] = useState<LocationFeature | null>(null);
  const [clickedCoords, setClickedCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);

  // Land access state
  const [landAccessData, setLandAccessData] = useState<LandAccessResponse | null>(null);
  const [landAccessLoading, setLandAccessLoading] = useState(false);
  const [landAccessError, setLandAccessError] = useState(false);
  const [showLandAccess, setShowLandAccess] = useState(false);

  const locationsQuery = useLocations();
  const featuresQuery  = useFeatures();
  const heatmapQuery   = useHeatmap();
  const scoreQuery     = useScore(clickedCoords?.lat ?? null, clickedCoords?.lon ?? null);

  const handleMapClick = useCallback((lat: number, lon: number) => {
    setSelectedFeature(null);
    setClickedCoords({ lat, lon });
  }, []);

  const handleLandAccessClick = useCallback(async (lat: number, lon: number) => {
    setShowLandAccess(true);
    setLandAccessLoading(true);
    setLandAccessError(false);
    setLandAccessData(null);
    try {
      const data = await fetchLandAccess(lat, lon);
      setLandAccessData(data);
    } catch {
      setLandAccessError(true);
    } finally {
      setLandAccessLoading(false);
    }
  }, []);

  const handleLandAccessOverride = useCallback(async (
    areaCode: string,
    status: 'allowed' | 'off_limits',
    notes: string,
  ) => {
    try {
      const updated = await putLandAccessOverride(areaCode, { status, notes });
      setLandAccessData(updated);
    } catch {
      // silently fail — user can retry
    }
  }, []);

  const handleCloseLandAccess = useCallback(() => {
    setShowLandAccess(false);
    setLandAccessData(null);
  }, []);

  const handleLocationSelect = useCallback((f: LocationFeature) => {
    setSelectedFeature(f);
    setClickedCoords(null);
  }, []);

  const handleCloseInfo  = useCallback(() => setSelectedFeature(null), []);
  const handleCloseScore = useCallback(() => setClickedCoords(null), []);

  const handleImportSuccess = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['locations'] });
    queryClient.invalidateQueries({ queryKey: ['features'] });
  }, [queryClient]);

  const locations      = locationsQuery.data?.features ?? [];
  const linearFeatures = featuresQuery.data?.features  ?? [];
  const heatmapPoints  = heatmapQuery.data             ?? [];

  const isInitialLoading =
    locationsQuery.isLoading || featuresQuery.isLoading || heatmapQuery.isLoading;

  return (
    <div className="relative w-screen h-screen bg-slate-950 overflow-hidden">
      {/* Navbar */}
      <Navbar
        locationCount={locations.length}
        isLoading={isInitialLoading}
        isLocationsError={locationsQuery.isError}
        isFeaturesError={featuresQuery.isError}
        onImportClick={() => setShowImportModal(true)}
      />

      {/* Full-screen map — offset below navbar */}
      <div className="absolute inset-0 top-12">
        <MapView
          locations={locations}
          linearFeatures={linearFeatures}
          heatmapPoints={heatmapPoints}
          layers={layers}
          onMapClick={handleMapClick}
          onLocationSelect={handleLocationSelect}
          onLandAccessClick={handleLandAccessClick}
        />
      </div>

      {/* Left panel: layer controls — offset below navbar */}
      <div className="absolute top-16 left-4 z-10">
        <LayerControls layers={layers} onChange={setLayers} />
      </div>

      {/* Bottom-right: info / score / land-access panels */}
      <div className="absolute bottom-6 right-6 z-10 flex flex-col gap-3 items-end">
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

        {showLandAccess && (
          <LandAccessPanel
            data={landAccessData}
            isLoading={landAccessLoading}
            isError={landAccessError}
            onClose={handleCloseLandAccess}
            onOverride={handleLandAccessOverride}
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

      {/* Import modal */}
      {showImportModal && (
        <ImportModal
          onClose={() => setShowImportModal(false)}
          onImportSuccess={handleImportSuccess}
        />
      )}
    </div>
  );
}
