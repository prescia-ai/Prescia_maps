import { useEffect, useRef } from 'react';
import { useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
// leaflet.heat patches the global L object as a side-effect
import 'leaflet.heat';
import type { HeatmapPoint } from '../types';

interface HeatmapLayerProps {
  points: HeatmapPoint[];
  visible: boolean;
}

// leaflet.heat attaches heatLayer to L after the side-effect import
type HeatLayerFn = (
  latlngs: [number, number, number][],
  options?: object,
) => L.Layer & { addTo(map: L.Map): L.Layer; remove(): void };

function getRadiusForZoom(zoom: number): number {
  // At z=4 (national): small radius so hotspots are distinct dots
  // At z=10+ (city level): large radius so the heat bleeds around sites
  if (zoom <= 4) return 8;
  if (zoom <= 6) return 15;
  if (zoom <= 8) return 22;
  if (zoom <= 10) return 30;
  if (zoom <= 12) return 40;
  return 50;
}

export default function HeatmapLayer({ points, visible }: HeatmapLayerProps) {
  const map = useMap();
  const heatRef = useRef<(L.Layer & { remove(): void }) | null>(null);

  function buildLayer() {
    const heatLayer = (L as unknown as { heatLayer: HeatLayerFn }).heatLayer;
    if (typeof heatLayer !== 'function') return null;

    const latlngs: [number, number, number][] = points.map(
      (p) => [p.lat, p.lon, p.weight],
    );

    const zoom = map.getZoom();
    const radius = getRadiusForZoom(zoom);

    return heatLayer(latlngs, {
      radius,
      blur: Math.round(radius * 0.7),
      maxZoom: 18,
      max: 1.0,
      // Green = highest value, yellow = medium, red = low (detecting potential)
      gradient: {
        0.0: '#1e3a5f',
        0.2: '#2563eb',
        0.4: '#16a34a',
        0.6: '#ca8a04',
        0.8: '#ea580c',
        1.0: '#dc2626',
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

  // Rebuild on zoom to get adaptive radius
  useMapEvents({
    zoomend() {
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
