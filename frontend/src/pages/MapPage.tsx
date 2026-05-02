import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import MapView from '../components/MapView';
import LayerControls from '../components/LayerControls';
import InfoPanel from '../components/InfoPanel';
import ScorePanel from '../components/ScorePanel';
import LandAccessPanel from '../components/LandAccessPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import Navbar from '../components/Navbar';
import ImportModal from '../components/ImportModal';
import MapContextMenu from '../components/MapContextMenu';
import PaywallModal from '../components/PaywallModal';
import { useLocations } from '../hooks/useLocations';
import { useFeatures } from '../hooks/useFeatures';
import { useScore } from '../hooks/useScore';
import { useMyPins } from '../hooks/useMyPins';
import { useAuth } from '../contexts/AuthContext';
import { putLandAccessOverride, fetchEventMapPins } from '../api/client';
import type { LocationFeature, LayerState, LandAccessResponse } from '../types';

const US_CENTER_LAT = 39.5;
const US_CENTER_LON = -98.35;

const DEFAULT_LAYERS: LayerState = {
  battle:          false,
  town:            false,
  mine:            false,
  camp:            false,
  railroad_stop:   false,
  stagecoach_stop: false,
  trail:           false,
  trail_landmark:  false,
  structure:       false,
  locale:          false,
  trading_post:    false,
  abandoned_fairground: false,
  pony_express:     false,
  abandoned_church: false,
  historic_brothel: false,
  ccc_camp:         false,
  homestead_site:   false,
  wwii_training:    false,
  wwi_training:     false,
  pow_camp:         false,
  railroad:         false,
  road:            false,
  blm:             false,
  aerials_1955:    false,
  my_hunts:        false,
  group_events:    false,
  huntPlans:       true,
  huntPlansArchived: false,
  grouped_trails:       false,
  grouped_stagecoach:   false,
  grouped_railroads:    false,
  grouped_pony_express: false,
};

export default function MapPage() {
  const queryClient = useQueryClient();
  const { user, isPro } = useAuth();
  const justSelectedFeatureRef = useRef(false);
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);

  // On mount: restore layer state from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('prescia_layer_state');
    if (saved) {
      try {
        setLayers(JSON.parse(saved));
      } catch {
        setLayers(DEFAULT_LAYERS);
      }
    }
  }, []);

  // Persist layer state to localStorage whenever it changes
  const handleLayerChange = useCallback((newLayers: LayerState) => {
    setLayers(newLayers);
    localStorage.setItem('prescia_layer_state', JSON.stringify(newLayers));
  }, []);
  const [selectedFeature, setSelectedFeature] = useState<LocationFeature | null>(null);
  const [clickedCoords, setClickedCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [contextMenuCoords, setContextMenuCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [contextMenuTab, setContextMenuTab] = useState<'log_hunt' | 'plan_hunt'>('log_hunt');
  const [showInsightPaywall, setShowInsightPaywall] = useState(false);

  // Land access state
  const [landAccessData, setLandAccessData] = useState<LandAccessResponse | null>(null);
  const landAccessLoading = false;
  const landAccessError = false;
  const [showLandAccess, setShowLandAccess] = useState(false);

  const locationsQuery = useLocations();
  const featuresQuery  = useFeatures();
  const scoreQuery     = useScore(clickedCoords?.lat ?? null, clickedCoords?.lon ?? null);
  const myPinsQuery    = useMyPins();
  const eventPinsQuery = useQuery({
    queryKey: ['event-map-pins'],
    queryFn: fetchEventMapPins,
    enabled: !!user,
  });

  const handleMapClick = useCallback((lat: number, lon: number) => {
    if (justSelectedFeatureRef.current) {
      justSelectedFeatureRef.current = false;
      return;
    }
    setSelectedFeature(null);
    if (!isPro) {
      setShowInsightPaywall(true);
      return;
    }
    setClickedCoords({ lat, lon });
  }, [isPro]);

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
    justSelectedFeatureRef.current = true;
    setSelectedFeature(f);
    setClickedCoords(null);
  }, []);

  const handleCloseInfo  = useCallback(() => setSelectedFeature(null), []);
  const handleCloseScore = useCallback(() => setClickedCoords(null), []);

  const handleImportSuccess = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['locations'] });
    queryClient.invalidateQueries({ queryKey: ['features'] });
  }, [queryClient]);

  const handleContextMenu = useCallback((lat: number, lon: number) => {
    if (user) {
      setContextMenuCoords({ lat, lon });
      setShowContextMenu(true);
    }
  }, [user]);

  const handleHuntSuccess = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['my-pins'] });
  }, [queryClient]);

  const handleNavbarLogHunt = useCallback(() => {
    setContextMenuCoords({ lat: US_CENTER_LAT, lon: US_CENTER_LON });
    setContextMenuTab('log_hunt');
    setShowContextMenu(true);
  }, []);

  const locations      = locationsQuery.data?.features ?? [];
  const linearFeatures = featuresQuery.data?.features  ?? [];
  const userPins       = (user && isPro && layers.my_hunts) ? (myPinsQuery.data?.pins ?? []) : [];
  const eventPins      = (user && isPro && layers.group_events) ? (eventPinsQuery.data ?? []) : [];

  const isInitialLoading =
    locationsQuery.isLoading || featuresQuery.isLoading;

  return (
    <div className="relative w-screen h-screen bg-stone-50 overflow-hidden">
      {/* Navbar */}
      <Navbar
        locationCount={locations.length}
        isLoading={isInitialLoading}
        isLocationsError={locationsQuery.isError}
        isFeaturesError={featuresQuery.isError}
        onImportClick={() => setShowImportModal(true)}
        onLogHuntClick={handleNavbarLogHunt}
      />

      {/* Full-screen map — offset below navbar */}
      <div className="absolute inset-0 top-14">
        <MapView
          locations={locations}
          linearFeatures={linearFeatures}
          layers={layers}
          onMapClick={handleMapClick}
          onLocationSelect={handleLocationSelect}
          onContextMenu={handleContextMenu}
          userPins={userPins}
          eventPins={eventPins}
          showHuntPlans={!!(user && isPro && layers.huntPlans)}
          showHuntPlansArchived={layers.huntPlansArchived}
        />
      </div>

      {/* Left panel: layer controls — offset below navbar */}
      <div className="absolute top-[4.5rem] left-4 z-10">
        <LayerControls layers={layers} onChange={handleLayerChange} />
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
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/80 backdrop-blur-sm">
          <div className="bg-white border border-stone-200 rounded-2xl px-10 py-8 shadow-xl">
            <LoadingSpinner message="Loading map data…" />
            <p className="text-xs text-stone-400 text-center mt-1">Connecting to backend API</p>
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

      {/* Site Insight paywall — shown when a free user clicks the map */}
      <PaywallModal
        open={showInsightPaywall}
        onClose={() => setShowInsightPaywall(false)}
        feature="Site Insight"
      />

      {/* Right-click / Log Hunt context menu */}
      {showContextMenu && contextMenuCoords && (
        <MapContextMenu
          lat={contextMenuCoords.lat}
          lon={contextMenuCoords.lon}
          onClose={() => setShowContextMenu(false)}
          onHuntSuccess={handleHuntSuccess}
          initialTab={contextMenuTab}
          onTabChange={setContextMenuTab}
        />
      )}
    </div>
  );
}
