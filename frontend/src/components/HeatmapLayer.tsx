import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
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

export default function HeatmapLayer({ points, visible }: HeatmapLayerProps) {
  const map = useMap();
  const heatRef = useRef<(L.Layer & { remove(): void }) | null>(null);

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const heatLayer = (L as unknown as { heatLayer: HeatLayerFn }).heatLayer;
    if (typeof heatLayer !== 'function') return;

    const latlngs: [number, number, number][] = points.map(
      (p) => [p.lat, p.lon, p.weight],
    );

    const layer = heatLayer(latlngs, {
      radius: 25,
      blur: 15,
      maxZoom: 12,
      gradient: { 0.2: '#3b82f6', 0.5: '#f59e0b', 0.8: '#ef4444', 1.0: '#7c3aed' },
    });

    heatRef.current = layer;

    if (visible) layer.addTo(map);

    return () => {
      layer.remove();
      heatRef.current = null;
    };
  // Rebuild when points or map instance change; visible toggling is handled below
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, points]);

  // Toggle visibility without re-creating the layer
  useEffect(() => {
    const layer = heatRef.current;
    if (!layer) return;

    if (visible) {
      layer.addTo(map);
    } else {
      layer.remove();
    }
  }, [map, visible]);

  return null;
}
