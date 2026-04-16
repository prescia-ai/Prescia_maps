import { useEffect, useRef } from 'react';
import { useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
// leaflet.heat patches the global L object as a side-effect
import 'leaflet.heat';
import type { HeatmapPoint } from '../types';

interface HeatmapLayerProps {
  points: HeatmapPoint[];
  visible: boolean;
  onZoomChange?: (zoom: number) => void;
}

// leaflet.heat attaches heatLayer to L after the side-effect import
type HeatLayerFn = (
  latlngs: [number, number, number][],
  options?: object,
) => L.Layer & { addTo(map: L.Map): L.Layer; remove(): void };

/**
 * Radius in pixels per zoom level.
 *
 * At mid zoom (8–12) we use a much larger radius so that two nearby
 * historical sites "bleed" into each other — the area between an old
 * town and a military camp should glow warm, not be cold.
 */
function getRadiusForZoom(zoom: number): number {
  if (zoom <= 5)  return 18;   // national: small tight dots
  if (zoom <= 7)  return 30;   // state: moderate dots
  if (zoom <= 9)  return 70;   // county: large blending radius
  if (zoom <= 11) return 90;   // town level: big overlap glow
  if (zoom <= 13) return 55;   // neighbourhood: medium precision
  return 30;                    // street: precise individual sites
}

function getBlurForZoom(zoom: number): number {
  if (zoom <= 7)  return 20;
  if (zoom <= 11) return 55;
  if (zoom <= 13) return 35;
  return 18;
}

function getOpacityForZoom(zoom: number): number {
  // More opaque at high zoom so precise hotspots pop
  if (zoom <= 7)  return 0.55;
  if (zoom <= 11) return 0.70;
  return 0.85;
}

export default function HeatmapLayer({ points, visible, onZoomChange }: HeatmapLayerProps) {
  const map = useMap();
  const heatRef = useRef<(L.Layer & { remove(): void }) | null>(null);

  function buildLayer() {
    const heatLayer = (L as unknown as { heatLayer: HeatLayerFn }).heatLayer;
    if (typeof heatLayer !== 'function') return null;

    const latlngs: [number, number, number][] = points.map(
      (p) => [p.lat, p.lon, p.weight],
    );

    const zoom = map.getZoom();
    const radius  = getRadiusForZoom(zoom);
    const blur    = getBlurForZoom(zoom);
    const opacity = getOpacityForZoom(zoom);

    return heatLayer(latlngs, {
      radius,
      blur,
      maxZoom: 18,
      max: 1.0,
      minOpacity: opacity * 0.3,
      // Treasure-density gradient: cold (deep blue) → warm (gold) → hot (red)
      // Designed to pop on both satellite and street map tiles.
      gradient: {
        0.00: 'rgba(0,0,80,0)',       // transparent — nothing interesting
        0.15: '#1e40af',              // dark blue — minimal activity
        0.35: '#0ea5e9',              // light blue — some activity
        0.55: '#fbbf24',              // amber/gold — good detecting area
        0.75: '#f97316',              // orange — strong historical area
        0.90: '#ef4444',              // red — exceptional hotspot
        1.00: '#dc2626',              // deep red — multiple converging sites
      },
    });
  }

  useEffect(() => {
    if (heatRef.current) {
      heatRef.current.remove();
      heatRef.current = null;
    }

    if (!visible || !points.length) return;

    const layer = buildLayer();
    if (!layer) return;
    heatRef.current = layer;
    layer.addTo(map);

    return () => {
      layer.remove();
      heatRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, points, visible]);

  // Rebuild on zoom to get adaptive radius/blur/opacity
  useMapEvents({
    zoomend() {
      const zoom = map.getZoom();

      // Notify parent so it can refetch data for the new zoom bucket
      onZoomChange?.(zoom);

      if (!visible || !points.length) return;
      if (heatRef.current) {
        heatRef.current.remove();
        heatRef.current = null;
      }
      const layer = buildLayer();
      if (!layer) return;
      heatRef.current = layer;
      layer.addTo(map);
    },
  });

  return null;
}
