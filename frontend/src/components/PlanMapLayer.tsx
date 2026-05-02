import { useEffect, useRef, useState } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import { createRoot } from 'react-dom/client';
import { usePlanMapPins } from '../hooks/useHuntPlans';
import { fetchPlan } from '../api/client';
import PlanMapPopup from './PlanMapPopup';
import type { HuntPlanMapPin, HuntPlanStatus } from '../types';
import { useAuth } from '../contexts/AuthContext';

// Status → fill color
const STATUS_FILL: Record<HuntPlanStatus, string> = {
  idea:     '#9ca3af', // gray
  planned:  '#3b82f6', // blue
  done:     '#22c55e', // green
  archived: '#d1d5db', // faded gray
};

// Site type → emoji label
const SITE_ICONS: Record<string, string> = {
  dirt:      '⛏',
  beach:     '🌊',
  water:     '💧',
  park:      '🌳',
  yard:      '🏡',
  club_hunt: '👥',
};

function makePinIcon(pin: HuntPlanMapPin): L.DivIcon {
  const fill = STATUS_FILL[pin.status] ?? '#9ca3af';
  const emoji = SITE_ICONS[pin.site_type ?? ''] ?? '📍';
  const opacity = pin.status === 'archived' ? 0.45 : 1;
  return L.divIcon({
    className: '',
    html: `<div style="
      display:flex;align-items:center;justify-content:center;
      width:28px;height:28px;border-radius:50%;
      background:${fill};border:2px solid white;
      box-shadow:0 1px 4px rgba(0,0,0,0.35);
      font-size:13px;opacity:${opacity};cursor:pointer;">
      ${emoji}
    </div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
}

// ── Polygon hover layer ───────────────────────────────────────────────────────

interface HoverPolygonProps {
  geojson: any;
}

function HoverPolygon({ geojson }: HoverPolygonProps) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    if (!geojson) return;
    const layer = L.geoJSON(geojson as any, {
      style: {
        color: '#f59e0b',
        weight: 2,
        fillOpacity: 0.08,
        opacity: 0.6,
        dashArray: '4 4',
      },
    }).addTo(map);
    layerRef.current = layer;
    return () => {
      map.removeLayer(layer);
      layerRef.current = null;
    };
  }, [map, geojson]);

  return null;
}

// ── Main component ─────────────────────────────────────────────────────────────

interface PlanMapLayerProps {
  includeArchived?: boolean;
}

export default function PlanMapLayer({ includeArchived = false }: PlanMapLayerProps) {
  const { isPro } = useAuth();
  const map = useMap();
  const { data: pins } = usePlanMapPins(includeArchived);
  const clusterGroupRef = useRef<any>(null);
  const [hoveredGeojson, setHoveredGeojson] = useState<any>(null);

  useEffect(() => {
    // For non-Pro users, ensure any lingering cluster group is removed and bail early.
    if (!isPro) {
      if (clusterGroupRef.current) {
        map.removeLayer(clusterGroupRef.current);
        clusterGroupRef.current = null;
      }
      return;
    }

    if (!pins) return;

    // Remove old cluster group
    if (clusterGroupRef.current) {
      map.removeLayer(clusterGroupRef.current);
    }

    // Create new cluster group
    const clusterGroup = (L as any).markerClusterGroup({
      maxClusterRadius: 50,
      showCoverageOnHover: false,
    });
    clusterGroupRef.current = clusterGroup;

    const roots: Array<ReturnType<typeof createRoot>> = [];

    for (const pin of pins) {
      const marker = L.marker([pin.lat, pin.lng], { icon: makePinIcon(pin) });

      // Hover: show polygon outline
      marker.on('mouseover', () => {
        if (pin.area_geojson) {
          setHoveredGeojson(pin.area_geojson);
        } else {
          // Fetch full plan to get area_geojson
          fetchPlan(pin.id)
            .then((full) => setHoveredGeojson(full.area_geojson))
            .catch((err) => {
              console.debug('Failed to fetch plan polygon for hover:', err);
            });
        }
      });
      marker.on('mouseout', () => {
        setHoveredGeojson(null);
      });

      // Click: popup — mount React eagerly into a detached node so Leaflet
      // sizes the popup correctly on first open and there is no async race.
      const container = document.createElement('div');
      const root = createRoot(container);
      root.render(
        <PlanMapPopup
          pin={pin}
          onClose={() => marker.closePopup()}
        />,
      );
      marker.bindPopup(container, { closeButton: true, minWidth: 200, maxWidth: 260 });

      // Track the root so we can unmount it when the cluster group is torn down.
      roots.push(root);

      clusterGroup.addLayer(marker);
    }

    map.addLayer(clusterGroup);

    return () => {
      if (clusterGroupRef.current) {
        map.removeLayer(clusterGroupRef.current);
        clusterGroupRef.current = null;
      }
      // Defer unmount to next tick so React doesn't warn about
      // unmounting a root that's mid-render.
      setTimeout(() => {
        for (const r of roots) {
          try { r.unmount(); } catch { /* ignore */ }
        }
      }, 0);
    };
  }, [map, pins, isPro]);

  return hoveredGeojson ? <HoverPolygon geojson={hoveredGeojson} /> : null;
}
