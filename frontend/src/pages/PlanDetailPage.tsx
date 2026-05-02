import { useEffect, useRef } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { MapContainer, Polygon, TileLayer, ZoomControl, useMap } from 'react-leaflet';
import L from 'leaflet';
import AppLayout from '../components/AppLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import { usePlan, useDeletePlan, useDuplicatePlan, useUpdatePlan, useUpdatePlanStatus } from '../hooks/useHuntPlans';
import { exportPlanGpx, exportPlanPdf } from '../api/client';
import type { HuntPlanStatus, InZoneMarker, ViewSnapshot } from '../types';

// ── Helpers ─────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<HuntPlanStatus, string> = {
  idea:     'bg-stone-100 text-stone-600',
  planned:  'bg-blue-100 text-blue-700',
  done:     'bg-green-100 text-green-700',
  archived: 'bg-stone-200 text-stone-500',
};

const MARKER_COLORS: Record<string, string> = {
  dig_target:       '#f59e0b',
  avoid:            '#ef4444',
  access:           '#3b82f6',
  already_detected: '#6b7280',
};

function extractPolygonPositions(geojson: any): [number, number][][] | null {
  try {
    const g = geojson?.type === 'Feature' ? geojson.geometry : geojson;
    if (!g) return null;
    if (g.type === 'Polygon') {
      return [g.coordinates[0].map(([lng, lat]: number[]) => [lat, lng] as [number, number])];
    }
    if (g.type === 'MultiPolygon') {
      return g.coordinates.map((poly: number[][][]) =>
        poly[0].map(([lng, lat]: number[]) => [lat, lng] as [number, number]),
      );
    }
  } catch {
    return null;
  }
  return null;
}

// ── Map view restorer ────────────────────────────────────────────────────────

function MapViewRestorer({ snapshot, geojson }: { snapshot: ViewSnapshot | null; geojson: any }) {
  const map = useMap();
  const didRestoreRef = useRef(false);
  useEffect(() => {
    if (didRestoreRef.current) return;
    didRestoreRef.current = true;
    if (snapshot) {
      map.setView(snapshot.center, snapshot.zoom);
    } else if (geojson) {
      // Fit map to polygon bounds
      try {
        const layer = L.geoJSON(geojson as any);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [40, 40] });
        }
      } catch {
        // ignore
      }
    }
  }, [map, snapshot, geojson]);
  return null;
}

// ── In-zone marker layer ─────────────────────────────────────────────────────

function InZoneMarkerLayer({ markers }: { markers: InZoneMarker[] }) {
  const map = useMap();
  const markerLayersRef = useRef<Map<string, L.Marker>>(new Map());

  useEffect(() => {
    const existing = markerLayersRef.current;

    // Remove stale
    for (const [id, layer] of existing) {
      if (!markers.find((m) => m.id === id)) {
        map.removeLayer(layer);
        existing.delete(id);
      }
    }

    // Add new
    for (const m of markers) {
      if (!existing.has(m.id)) {
        const icon = L.divIcon({
          className: '',
          html: `<div style="width:10px;height:10px;border-radius:50%;background:${MARKER_COLORS[m.type] ?? '#94a3b8'};border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.4)"></div>`,
          iconSize: [10, 10],
          iconAnchor: [5, 5],
        });
        const marker = L.marker([m.lat, m.lng], { icon }).addTo(map);
        marker.bindPopup(
          `<strong>${m.label}</strong><br/><em>${m.type.replace('_', ' ')}</em>${m.note ? `<br/>${m.note}` : ''}`,
        );
        existing.set(m.id, marker);
      }
    }

    return () => {
      for (const [, layer] of existing) {
        map.removeLayer(layer);
      }
      existing.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, markers]);

  return null;
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function PlanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: plan, isLoading, isError } = usePlan(id);

  const deleteMutation = useDeletePlan();
  const duplicateMutation = useDuplicatePlan();
  const updateMutation = useUpdatePlan();
  const statusMutation = useUpdatePlanStatus();

  async function handleDelete() {
    if (!plan || !confirm(`Delete "${plan.title}"? This cannot be undone.`)) return;
    await deleteMutation.mutateAsync(plan.id);
    navigate('/plans');
  }

  async function handleDuplicate() {
    if (!plan) return;
    const copy = await duplicateMutation.mutateAsync(plan.id);
    navigate(`/plans/${copy.id}`);
  }

  async function handleStatusChange(newStatus: HuntPlanStatus) {
    if (!plan) return;
    await statusMutation.mutateAsync({ planId: plan.id, status: newStatus });
  }

  async function handleGearToggle(idx: number) {
    if (!plan?.gear_checklist) return;
    const updated = plan.gear_checklist.map((g, i) =>
      i === idx ? { ...g, checked: !g.checked } : g,
    );
    await updateMutation.mutateAsync({
      planId: plan.id,
      payload: { gear_checklist: updated },
    });
  }

  if (isLoading) {
    return (
      <AppLayout>
        <div className="flex justify-center py-24">
          <LoadingSpinner message="Loading plan…" />
        </div>
      </AppLayout>
    );
  }

  if (isError || !plan) {
    return (
      <AppLayout>
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <h1 className="text-lg font-semibold text-stone-900 mb-2">Plan not found</h1>
          <Link to="/plans" className="text-amber-600 hover:underline text-sm">
            Back to Plans
          </Link>
        </div>
      </AppLayout>
    );
  }

  const polygonPositions = extractPolygonPositions(plan.area_geojson);
  const dateLabel = plan.planned_date
    ? new Date(plan.planned_date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  return (
    <AppLayout>
      <div className="flex h-[calc(100vh-3rem)] overflow-hidden">
        {/* Map panel */}
        <div className="flex-1 relative">
          <MapContainer
            center={[39.5, -98.35]}
            zoom={5}
            className="w-full h-full"
            zoomControl={false}
          >
            <ZoomControl position="bottomright" />
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              maxZoom={19}
            />
            <MapViewRestorer snapshot={plan.view_snapshot} geojson={plan.area_geojson} />

            {polygonPositions && polygonPositions.map((positions, i) => (
              <Polygon
                key={i}
                positions={positions}
                pathOptions={{
                  color: '#f59e0b',
                  fillColor: '#fef3c7',
                  fillOpacity: 0.2,
                  weight: 2,
                }}
              />
            ))}

            {plan.in_zone_markers && plan.in_zone_markers.length > 0 && (
              <InZoneMarkerLayer markers={plan.in_zone_markers} />
            )}
          </MapContainer>
        </div>

        {/* Detail panel */}
        <div className="w-80 xl:w-96 border-l border-stone-200 bg-white overflow-y-auto flex flex-col">
          {/* Header */}
          <div className="p-4 border-b border-stone-100">
            <div className="flex items-start justify-between gap-2 mb-2">
              <h1 className="text-base font-semibold text-stone-900 leading-tight">
                {plan.title}
              </h1>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide flex-shrink-0 ${STATUS_COLORS[plan.status]}`}
              >
                {plan.status}
              </span>
            </div>

            {/* Meta */}
            <div className="flex flex-wrap gap-2 text-xs text-stone-500">
              {plan.site_type && (
                <span className="bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded font-medium">
                  {plan.site_type.replace('_', ' ')}
                </span>
              )}
              {dateLabel && <span>📅 {dateLabel}</span>}
            </div>
          </div>

          <div className="flex-1 p-4 space-y-5 text-sm">
            {/* Status changer */}
            <div>
              <span className="text-xs font-medium text-stone-600 block mb-1.5">Status</span>
              <div className="grid grid-cols-4 gap-1">
                {(['idea', 'planned', 'done', 'archived'] as HuntPlanStatus[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => handleStatusChange(s)}
                    className={`px-1.5 py-1 rounded text-[11px] font-medium transition-colors ${
                      plan.status === s
                        ? 'bg-amber-600 text-white'
                        : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                    }`}
                  >
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-1.5">
              <Link
                to={`/plans/${plan.id}/edit`}
                className="px-3 py-1.5 text-xs bg-stone-100 text-stone-700 rounded-lg hover:bg-stone-200 transition-colors"
              >
                Edit
              </Link>
              <button
                onClick={handleDuplicate}
                className="px-3 py-1.5 text-xs bg-stone-100 text-stone-700 rounded-lg hover:bg-stone-200 transition-colors"
              >
                Duplicate
              </button>
              <button
                onClick={() => exportPlanGpx(plan.id)}
                className="px-3 py-1.5 text-xs bg-stone-100 text-stone-700 rounded-lg hover:bg-stone-200 transition-colors"
              >
                Export GPX
              </button>
              <button
                onClick={() => exportPlanPdf(plan.id)}
                className="px-3 py-1.5 text-xs bg-stone-100 text-stone-700 rounded-lg hover:bg-stone-200 transition-colors"
              >
                Export PDF
              </button>
              <button
                onClick={handleDelete}
                className="px-3 py-1.5 text-xs bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors"
              >
                Delete
              </button>
            </div>

            {/* Notes */}
            {plan.notes && (
              <div>
                <span className="text-xs font-medium text-stone-600 block mb-1">Notes</span>
                <p className="text-sm text-stone-700 whitespace-pre-wrap">{plan.notes}</p>
              </div>
            )}

            {/* In-zone markers */}
            {plan.in_zone_markers && plan.in_zone_markers.length > 0 && (
              <div>
                <span className="text-xs font-medium text-stone-600 block mb-2">In-Zone Markers</span>
                <ul className="space-y-1.5">
                  {plan.in_zone_markers.map((m) => (
                    <li key={m.id} className="flex items-start gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5"
                        style={{ backgroundColor: MARKER_COLORS[m.type] ?? '#94a3b8' }}
                      />
                      <div className="flex-1">
                        <span className="text-xs font-medium text-stone-800">{m.label}</span>
                        <span className="text-[10px] text-stone-400 ml-1">
                          ({m.type.replace('_', ' ')})
                        </span>
                        {m.note && <p className="text-[11px] text-stone-500 mt-0.5">{m.note}</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Gear checklist */}
            {plan.gear_checklist && plan.gear_checklist.length > 0 && (
              <div>
                <span className="text-xs font-medium text-stone-600 block mb-2">Gear Checklist</span>
                <ul className="space-y-1.5">
                  {plan.gear_checklist.map((item, idx) => (
                    <li key={idx} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={item.checked}
                        onChange={() => handleGearToggle(idx)}
                        className="rounded border-stone-300"
                      />
                      <span
                        className={`text-sm ${item.checked ? 'line-through text-stone-400' : 'text-stone-700'}`}
                      >
                        {item.item}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Permission info */}
            {plan.permission && Object.values(plan.permission).some(Boolean) && (
              <div>
                <span className="text-xs font-medium text-stone-600 block mb-2">
                  Permission Info
                </span>
                <dl className="space-y-1">
                  {plan.permission.owner_name && (
                    <div className="flex gap-2">
                      <dt className="text-[11px] text-stone-500 w-24 flex-shrink-0">Landowner</dt>
                      <dd className="text-[11px] text-stone-700">{plan.permission.owner_name}</dd>
                    </div>
                  )}
                  {plan.permission.contact && (
                    <div className="flex gap-2">
                      <dt className="text-[11px] text-stone-500 w-24 flex-shrink-0">Contact</dt>
                      <dd className="text-[11px] text-stone-700">{plan.permission.contact}</dd>
                    </div>
                  )}
                  {plan.permission.status && (
                    <div className="flex gap-2">
                      <dt className="text-[11px] text-stone-500 w-24 flex-shrink-0">Status</dt>
                      <dd className="text-[11px] text-stone-700">{plan.permission.status}</dd>
                    </div>
                  )}
                  {plan.permission.expiry && (
                    <div className="flex gap-2">
                      <dt className="text-[11px] text-stone-500 w-24 flex-shrink-0">Expires</dt>
                      <dd className="text-[11px] text-stone-700">{plan.permission.expiry}</dd>
                    </div>
                  )}
                  {plan.permission.notes && (
                    <div className="flex gap-2">
                      <dt className="text-[11px] text-stone-500 w-24 flex-shrink-0">Notes</dt>
                      <dd className="text-[11px] text-stone-700">{plan.permission.notes}</dd>
                    </div>
                  )}
                </dl>
              </div>
            )}

            {/* Photos */}
            {plan.photo_urls && plan.photo_urls.length > 0 && (
              <div>
                <span className="text-xs font-medium text-stone-600 block mb-2">Photos</span>
                <div className="grid grid-cols-2 gap-1.5">
                  {plan.photo_urls.map((url, i) => (
                    <a key={i} href={url} target="_blank" rel="noopener noreferrer">
                      <img
                        src={url}
                        alt={`Photo ${i + 1}`}
                        className="w-full h-20 object-cover rounded-lg hover:opacity-90 transition-opacity"
                      />
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer nav */}
          <div className="p-4 border-t border-stone-100">
            <Link
              to="/plans"
              className="text-xs text-stone-500 hover:text-stone-700 flex items-center gap-1"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Plans
            </Link>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
