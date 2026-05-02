import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  MapContainer,
  TileLayer,
  useMap,
  ZoomControl,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet-draw';
import 'leaflet-draw/dist/leaflet.draw.css';
import AppLayout from '../components/AppLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import { useCreatePlan, useUpdatePlan } from '../hooks/useHuntPlans';
import { usePlan } from '../hooks/useHuntPlans';
import { uploadPinImages } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import type { GearItem, InZoneMarker, PermissionInfo, ViewSnapshot } from '../types';

// ── Drawing control ─────────────────────────────────────────────────────────

interface DrawControlProps {
  onShapeDrawn: (geojson: object) => void;
  onMarkersOutside?: (ids: string[]) => void;
  inZoneMarkers: InZoneMarker[];
}

function DrawControl({ onShapeDrawn, inZoneMarkers }: DrawControlProps) {
  const map = useMap();
  const drawnItemsRef = useRef<L.FeatureGroup>(new L.FeatureGroup());
  const markerLayersRef = useRef<Map<string, L.Marker>>(new Map());

  useEffect(() => {
    const drawnItems = drawnItemsRef.current;
    map.addLayer(drawnItems);

    const drawControl = new (L.Control as any).Draw({
      edit: { featureGroup: drawnItems },
      draw: {
        polygon: true,
        rectangle: true,
        circle: true,
        polyline: false,
        marker: false,
        circlemarker: false,
      },
    });
    map.addControl(drawControl);

    function onDrawCreated(e: any) {
      // Only one shape at a time — clear previous
      drawnItems.clearLayers();
      const layer = e.layer;
      drawnItems.addLayer(layer);
      const geojson = layer.toGeoJSON();
      // For circles, annotate with radius
      if (e.layerType === 'circle') {
        geojson.properties = geojson.properties ?? {};
        geojson.properties.radius = (layer as L.Circle).getRadius();
      }
      onShapeDrawn(geojson);
    }

    function onDrawEdited(e: any) {
      const layers = e.layers;
      layers.eachLayer((layer: any) => {
        const geojson = layer.toGeoJSON();
        if (layer instanceof L.Circle) {
          geojson.properties = geojson.properties ?? {};
          geojson.properties.radius = layer.getRadius();
        }
        onShapeDrawn(geojson);
      });
    }

    map.on((L as any).Draw.Event.CREATED, onDrawCreated);
    map.on((L as any).Draw.Event.EDITED, onDrawEdited);

    return () => {
      map.off((L as any).Draw.Event.CREATED, onDrawCreated);
      map.off((L as any).Draw.Event.EDITED, onDrawEdited);
      map.removeControl(drawControl);
      map.removeLayer(drawnItems);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  // Render in-zone markers on the map
  useEffect(() => {
    const markerLayers = markerLayersRef.current;

    // Remove stale markers
    for (const [id, marker] of markerLayers) {
      if (!inZoneMarkers.find((m) => m.id === id)) {
        map.removeLayer(marker);
        markerLayers.delete(id);
      }
    }

    // Add new markers
    for (const m of inZoneMarkers) {
      if (!markerLayers.has(m.id)) {
        const markerIcon = L.divIcon({
          className: '',
          html: `<div style="width:10px;height:10px;border-radius:50%;background:${MARKER_COLORS[m.type]};border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.4)"></div>`,
          iconSize: [10, 10],
          iconAnchor: [5, 5],
        });
        const marker = L.marker([m.lat, m.lng], { icon: markerIcon }).addTo(map);
        marker.bindTooltip(m.label || m.type);
        markerLayers.set(m.id, marker);
      }
    }
  }, [inZoneMarkers, map]);

  return null;
}

const MARKER_COLORS: Record<string, string> = {
  dig_target:       '#f59e0b',
  avoid:            '#ef4444',
  access:           '#3b82f6',
  already_detected: '#6b7280',
};

// ── In-zone marker capture handler ─────────────────────────────────────────

interface MarkerDropHandlerProps {
  active: boolean;
  pendingType: InZoneMarker['type'];
  onMarkerDropped: (lat: number, lng: number) => void;
}

function MarkerDropHandler({ active, pendingType, onMarkerDropped }: MarkerDropHandlerProps) {
  const map = useMap();
  useEffect(() => {
    if (!active) {
      map.getContainer().style.cursor = '';
      return;
    }
    map.getContainer().style.cursor = 'crosshair';
    function onClick(e: L.LeafletMouseEvent) {
      onMarkerDropped(e.latlng.lat, e.latlng.lng);
    }
    map.once('click', onClick);
    return () => {
      map.off('click', onClick);
      map.getContainer().style.cursor = '';
    };
  }, [active, pendingType, onMarkerDropped, map]);
  return null;
}

// ── View snapshot capture ───────────────────────────────────────────────────

function ViewSnapshotCapture({
  onSnapshot,
  layerState,
}: {
  onSnapshot: (snap: ViewSnapshot) => void;
  layerState: Record<string, boolean>;
}) {
  const map = useMap();
  useEffect(() => {
    function capture() {
      const center = map.getCenter();
      onSnapshot({
        center: [center.lat, center.lng],
        zoom: map.getZoom(),
        layers: layerState,
      });
    }
    map.on('moveend', capture);
    map.on('zoomend', capture);
    return () => {
      map.off('moveend', capture);
      map.off('zoomend', capture);
    };
  }, [map, onSnapshot, layerState]);
  return null;
}

// ── Map center setter on initial load ──────────────────────────────────────

function MapCenterSetter({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  const didSetRef = useRef(false);
  useEffect(() => {
    if (!didSetRef.current) {
      didSetRef.current = true;
      map.setView([lat, lng], 14);
    }
  }, [map, lat, lng]);
  return null;
}

// ── Main page ───────────────────────────────────────────────────────────────

interface CreatePlanPageProps {
  planId?: string;
}

export default function CreatePlanPage({ planId }: CreatePlanPageProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { profile } = useAuth();

  // Pre-seed lat/lng from query params (right-click flow)
  const seedLat = parseFloat(searchParams.get('lat') ?? '39.5');
  const seedLng = parseFloat(searchParams.get('lng') ?? '-98.35');
  const initialLat = isNaN(seedLat) ? 39.5 : seedLat;
  const initialLng = isNaN(seedLng) ? -98.35 : seedLng;

  // Edit mode: load existing plan
  const { data: existingPlan, isLoading: planLoading } = usePlan(planId);

  // Form state
  const [title, setTitle] = useState('');
  const [plannedDate, setPlannedDate] = useState('');
  const [siteType, setSiteType] = useState('');
  const [notes, setNotes] = useState('');
  const [areaGeojson, setAreaGeojson] = useState<object | null>(null);
  const [inZoneMarkers, setInZoneMarkers] = useState<InZoneMarker[]>([]);
  const [gearChecklist, setGearChecklist] = useState<GearItem[]>([]);
  const [permission, setPermission] = useState<PermissionInfo>({
    owner_name: null, contact: null, status: null, expiry: null, notes: null,
  });
  const [photoUrls, setPhotoUrls] = useState<string[]>([]);
  const [viewSnapshot, setViewSnapshot] = useState<ViewSnapshot | null>(null);
  const [layerState] = useState<Record<string, boolean>>({});

  // Marker drop state
  const [droppingMarker, setDroppingMarker] = useState(false);
  const [pendingMarkerType, setPendingMarkerType] = useState<InZoneMarker['type']>('dig_target');
  const [pendingMarkerLabel, setPendingMarkerLabel] = useState('');
  const [pendingMarkerNote, setPendingMarkerNote] = useState('');
  const [showMarkerForm, setShowMarkerForm] = useState(false);
  const [droppedCoords, setDroppedCoords] = useState<{ lat: number; lng: number } | null>(null);

  // Gear checklist
  const [newGearItem, setNewGearItem] = useState('');

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Image upload
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [imagePreviews, setImagePreviews] = useState<string[]>([]);
  const previewUrlsRef = useRef<string[]>([]);
  const googleConnected = !!profile?.google_connected_at;

  const createMutation = useCreatePlan();
  const updateMutation = useUpdatePlan();

  // Populate form when editing
  useEffect(() => {
    if (!existingPlan) return;
    setTitle(existingPlan.title);
    setPlannedDate(existingPlan.planned_date ? existingPlan.planned_date.split('T')[0] : '');
    setSiteType(existingPlan.site_type ?? '');
    setNotes(existingPlan.notes ?? '');
    setAreaGeojson(existingPlan.area_geojson ?? null);
    setInZoneMarkers(existingPlan.in_zone_markers ?? []);
    setGearChecklist(existingPlan.gear_checklist ?? []);
    setPermission(existingPlan.permission ?? { owner_name: null, contact: null, status: null, expiry: null, notes: null });
    setPhotoUrls(existingPlan.photo_urls ?? []);
  }, [existingPlan]);

  const handleShapeDrawn = useCallback((geojson: object) => {
    setAreaGeojson(geojson);
  }, []);

  const handleSnapshotCapture = useCallback(
    (snap: ViewSnapshot) => {
      setViewSnapshot({ ...snap, layers: layerState });
    },
    [layerState],
  );

  function handleMarkerDrop(lat: number, lng: number) {
    setDroppedCoords({ lat, lng });
    setDroppingMarker(false);
    setShowMarkerForm(true);
  }

  function confirmMarker() {
    if (!droppedCoords) return;
    const marker: InZoneMarker = {
      id: crypto.randomUUID(),
      lat: droppedCoords.lat,
      lng: droppedCoords.lng,
      type: pendingMarkerType,
      label: pendingMarkerLabel || pendingMarkerType,
      note: pendingMarkerNote || null,
    };
    setInZoneMarkers((prev) => [...prev, marker]);
    setShowMarkerForm(false);
    setPendingMarkerLabel('');
    setPendingMarkerNote('');
    setDroppedCoords(null);
  }

  function removeMarker(id: string) {
    setInZoneMarkers((prev) => prev.filter((m) => m.id !== id));
  }

  function addGearItem() {
    if (!newGearItem.trim()) return;
    setGearChecklist((prev) => [...prev, { item: newGearItem.trim(), checked: false }]);
    setNewGearItem('');
  }

  function toggleGearItem(idx: number) {
    setGearChecklist((prev) =>
      prev.map((g, i) => (i === idx ? { ...g, checked: !g.checked } : g)),
    );
  }

  function removeGearItem(idx: number) {
    setGearChecklist((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleImageSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    if (!selected.length) return;
    const combined = [...imageFiles, ...selected].slice(0, 4);
    setImageFiles(combined);

    // Revoke old blob URLs
    for (const url of previewUrlsRef.current) URL.revokeObjectURL(url);

    // Use FileReader to produce validated data URLs (prevents XSS from crafted SVGs via blob URLs)
    const previews: string[] = [];
    let done = 0;
    for (let i = 0; i < combined.length; i++) {
      const reader = new FileReader();
      const idx = i;
      reader.onload = (ev) => {
        const result = ev.target?.result as string | null;
        // Only accept data URLs with an image/* MIME type
        if (result && /^data:image\//.test(result)) {
          previews[idx] = result;
        } else {
          previews[idx] = '';
        }
        done++;
        if (done === combined.length) {
          previewUrlsRef.current = [];
          setImagePreviews(previews);
        }
      };
      reader.readAsDataURL(combined[i]);
    }
    e.target.value = '';
  }

  async function handleSave() {
    if (!title.trim()) {
      setError('Title is required.');
      return;
    }
    if (!areaGeojson) {
      setError('Please draw a zone on the map first.');
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      let uploadedUrls: string[] = [...photoUrls];

      const payload = {
        title: title.trim(),
        area_geojson: areaGeojson,
        planned_date: plannedDate || null,
        site_type: siteType || null,
        notes: notes || null,
        in_zone_markers: inZoneMarkers.length ? inZoneMarkers : null,
        gear_checklist: gearChecklist.length ? gearChecklist : null,
        permission: Object.values(permission).some(Boolean) ? permission : null,
        view_snapshot: viewSnapshot,
        photo_urls: uploadedUrls.length ? uploadedUrls : null,
      };

      let saved;
      if (planId) {
        saved = await updateMutation.mutateAsync({ planId, payload });
      } else {
        saved = await createMutation.mutateAsync(payload);
      }

      // Upload images if any
      if (imageFiles.length > 0 && googleConnected) {
        try {
          const result = await uploadPinImages(saved.id, imageFiles);
          const newUrls = result.images.map((img) => img.url);
          await updateMutation.mutateAsync({
            planId: saved.id,
            payload: { photo_urls: [...uploadedUrls, ...newUrls] },
          });
        } catch {
          // Image upload failed — plan still saved
        }
      }

      navigate(`/plans/${saved.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to save plan. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  if (planId && planLoading) {
    return (
      <AppLayout>
        <div className="flex justify-center py-24">
          <LoadingSpinner message="Loading plan…" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="flex h-[calc(100vh-3rem)] overflow-hidden">
        {/* Map panel */}
        <div className="flex-1 relative">
          <MapContainer
            center={[initialLat, initialLng]}
            zoom={14}
            className="w-full h-full"
            zoomControl={false}
          >
            <ZoomControl position="bottomright" />
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              maxZoom={19}
            />
            {(searchParams.get('lat') || searchParams.get('lng')) && (
              <MapCenterSetter lat={initialLat} lng={initialLng} />
            )}
            <DrawControl
              onShapeDrawn={handleShapeDrawn}
              inZoneMarkers={inZoneMarkers}
            />
            <MarkerDropHandler
              active={droppingMarker}
              pendingType={pendingMarkerType}
              onMarkerDropped={handleMarkerDrop}
            />
            <ViewSnapshotCapture
              onSnapshot={handleSnapshotCapture}
              layerState={layerState}
            />
          </MapContainer>

          {/* Drawing hint */}
          {!areaGeojson && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-white/90 backdrop-blur-sm border border-stone-200 rounded-xl px-4 py-2 shadow text-xs text-stone-600 pointer-events-none">
              Use the drawing toolbar to draw your hunt zone
            </div>
          )}
        </div>

        {/* Form panel */}
        <div className="w-80 xl:w-96 border-l border-stone-200 bg-white overflow-y-auto flex flex-col">
          <div className="p-4 border-b border-stone-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-stone-900">
              {planId ? 'Edit Plan' : 'New Plan'}
            </h2>
            <button
              onClick={() => navigate(planId ? `/plans/${planId}` : '/plans')}
              className="text-stone-400 hover:text-stone-600"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex-1 p-4 space-y-4 text-sm">
            {/* Zone status */}
            <div
              className={`rounded-lg px-3 py-2 text-xs font-medium ${
                areaGeojson
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-amber-50 text-amber-700 border border-amber-200'
              }`}
            >
              {areaGeojson ? '✓ Zone drawn' : '⚠ Draw a zone on the map (required)'}
            </div>

            {/* Title */}
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">
                Title <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Hunt plan title"
                className="w-full border border-stone-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-stone-400"
              />
            </div>

            {/* Planned date */}
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">
                Planned Date (optional)
              </label>
              <input
                type="date"
                value={plannedDate}
                onChange={(e) => setPlannedDate(e.target.value)}
                className="w-full border border-stone-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-stone-400"
              />
            </div>

            {/* Site type */}
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">
                Site Type
              </label>
              <select
                value={siteType}
                onChange={(e) => setSiteType(e.target.value)}
                className="w-full border border-stone-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-stone-400 bg-white"
              >
                <option value="">Select…</option>
                <option value="dirt">Dirt</option>
                <option value="beach">Beach</option>
                <option value="water">Water</option>
                <option value="park">Park</option>
                <option value="yard">Yard</option>
                <option value="club_hunt">Club Hunt</option>
              </select>
            </div>

            {/* Notes */}
            <div>
              <label className="block text-xs font-medium text-stone-700 mb-1">Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Research notes, site history, access details…"
                className="w-full border border-stone-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-stone-400 resize-none"
              />
            </div>

            {/* In-zone markers */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-stone-700">In-Zone Markers</span>
              </div>
              <div className="flex gap-2 mb-2">
                <select
                  value={pendingMarkerType}
                  onChange={(e) => setPendingMarkerType(e.target.value as InZoneMarker['type'])}
                  className="flex-1 border border-stone-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-stone-400 bg-white"
                >
                  <option value="dig_target">Dig Target</option>
                  <option value="avoid">Avoid</option>
                  <option value="access">Access</option>
                  <option value="already_detected">Already Detected</option>
                </select>
                <button
                  onClick={() => setDroppingMarker(true)}
                  disabled={!areaGeojson}
                  className="px-2 py-1.5 text-xs bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title={!areaGeojson ? 'Draw a zone first' : 'Click on map to place marker'}
                >
                  {droppingMarker ? 'Click map…' : '+ Drop'}
                </button>
              </div>

              {/* Marker form after drop */}
              {showMarkerForm && (
                <div className="border border-stone-200 rounded-lg p-3 mb-2 bg-stone-50">
                  <p className="text-xs text-stone-600 mb-2">
                    Placed at {droppedCoords?.lat.toFixed(5)}, {droppedCoords?.lng.toFixed(5)}
                  </p>
                  <input
                    type="text"
                    value={pendingMarkerLabel}
                    onChange={(e) => setPendingMarkerLabel(e.target.value)}
                    placeholder="Label"
                    className="w-full border border-stone-200 rounded px-2 py-1 text-xs mb-1.5 focus:outline-none"
                  />
                  <input
                    type="text"
                    value={pendingMarkerNote}
                    onChange={(e) => setPendingMarkerNote(e.target.value)}
                    placeholder="Note (optional)"
                    className="w-full border border-stone-200 rounded px-2 py-1 text-xs mb-2 focus:outline-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={confirmMarker}
                      className="flex-1 py-1 text-xs bg-amber-600 text-white rounded hover:bg-amber-700"
                    >
                      Add
                    </button>
                    <button
                      onClick={() => {
                        setShowMarkerForm(false);
                        setDroppedCoords(null);
                      }}
                      className="flex-1 py-1 text-xs bg-stone-200 text-stone-700 rounded hover:bg-stone-300"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Marker list */}
              {inZoneMarkers.length > 0 && (
                <ul className="space-y-1">
                  {inZoneMarkers.map((m) => (
                    <li key={m.id} className="flex items-center gap-1.5">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: MARKER_COLORS[m.type] }}
                      />
                      <span className="flex-1 text-xs text-stone-700 truncate">{m.label}</span>
                      <span className="text-[10px] text-stone-400">{m.type.replace('_', ' ')}</span>
                      <button
                        onClick={() => removeMarker(m.id)}
                        className="text-stone-400 hover:text-red-500"
                      >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Gear checklist */}
            <div>
              <span className="text-xs font-medium text-stone-700 block mb-1">Gear Checklist</span>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={newGearItem}
                  onChange={(e) => setNewGearItem(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addGearItem()}
                  placeholder="Add item…"
                  className="flex-1 border border-stone-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-stone-400"
                />
                <button
                  onClick={addGearItem}
                  className="px-2 py-1.5 text-xs bg-stone-100 text-stone-700 rounded-lg hover:bg-stone-200"
                >
                  +
                </button>
              </div>
              {gearChecklist.length > 0 && (
                <ul className="space-y-1">
                  {gearChecklist.map((item, idx) => (
                    <li key={idx} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={item.checked}
                        onChange={() => toggleGearItem(idx)}
                        className="rounded border-stone-300"
                      />
                      <span className="flex-1 text-xs text-stone-700">{item.item}</span>
                      <button onClick={() => removeGearItem(idx)} className="text-stone-400 hover:text-red-500">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Permission info */}
            <div>
              <span className="text-xs font-medium text-stone-700 block mb-1">Permission Info</span>
              {(
                [
                  ['owner_name', 'Landowner Name'],
                  ['contact', 'Contact'],
                  ['status', 'Permission Status'],
                  ['expiry', 'Expiry'],
                  ['notes', 'Notes'],
                ] as [keyof PermissionInfo, string][]
              ).map(([field, label]) => (
                <div key={field} className="mb-1.5">
                  <input
                    type="text"
                    value={permission[field] ?? ''}
                    onChange={(e) =>
                      setPermission((prev) => ({ ...prev, [field]: e.target.value || null }))
                    }
                    placeholder={label}
                    className="w-full border border-stone-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-stone-400"
                  />
                </div>
              ))}
            </div>

            {/* Photos */}
            {googleConnected && (
              <div>
                <span className="text-xs font-medium text-stone-700 block mb-1">Photos</span>
                <label className="flex items-center gap-1.5 px-3 py-1.5 border border-stone-200 rounded-lg cursor-pointer hover:bg-stone-50 transition-colors">
                  <svg className="w-4 h-4 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <span className="text-xs text-stone-600">Add photos (max 4, via Google Drive)</span>
                  <input type="file" accept="image/*" multiple className="hidden" onChange={handleImageSelect} />
                </label>
                {imagePreviews.length > 0 && (
                  <div className="grid grid-cols-2 gap-1 mt-2">
                    {imagePreviews.map((dataUrl, i) =>
                      dataUrl ? (
                        <img key={i} src={dataUrl} className="w-full h-16 object-cover rounded" alt="" />
                      ) : null,
                    )}
                  </div>
                )}
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg px-3 py-2">
                {error}
              </div>
            )}
          </div>

          {/* Save button */}
          <div className="p-4 border-t border-stone-100">
            <button
              onClick={handleSave}
              disabled={submitting || !title.trim() || !areaGeojson}
              className="w-full py-2.5 bg-amber-600 hover:bg-amber-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
            >
              {submitting ? 'Saving…' : planId ? 'Save Changes' : 'Save Plan'}
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
