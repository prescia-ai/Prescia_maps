import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import * as maplibregl from 'maplibre-gl';
import '@maplibre/maplibre-gl-leaflet';
import L from 'leaflet';

interface LandAccessOverlayProps {
  visible: boolean;
}

// Keep getAccessLabel exported in case other components use it.
export function getAccessLabel(agency: string): string {
  const ag = (agency || '').toUpperCase();

  // RED: Off Limits
  if (ag === 'NPS' || ag === 'FWS' || ag === 'DOD') return 'Off Limits';

  // GREEN: Public OK
  if (ag === 'BLM' || ag === 'USFS' || ag === 'BOR') return 'Public — OK to Detect';

  // YELLOW: State/Local
  if (ag.includes('STATE') || ag.includes('STAT') || ag.includes('LOC') || ag.includes('CNTY')) return 'Private — Permit Required';

  return 'Unsure — Verify First';
}

const MIN_ZOOM = 9;

// MapLibre fill-color expression that ports the getAccessColor logic.
const FILL_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  'case',
  // RED: NPS, FWS, DOD — always off-limits
  ['any',
    ['==', ['get', 'agency'], 'NPS'],
    ['==', ['get', 'agency'], 'FWS'],
    ['==', ['get', 'agency'], 'DOD'],
  ], '#ef4444',
  // GREEN: BLM, USFS, or Bureau of Reclamation
  ['any',
    ['==', ['get', 'agency'], 'BLM'],
    ['==', ['get', 'agency'], 'USFS'],
    ['==', ['get', 'agency'], 'BOR'],
  ], '#22c55e',
  // YELLOW: State / local government land
  ['any',
    ['in', 'STATE', ['upcase', ['to-string', ['get', 'agency']]]],
    ['in', 'STAT', ['upcase', ['to-string', ['get', 'agency']]]],
    ['in', 'LOC', ['upcase', ['to-string', ['get', 'agency']]]],
    ['in', 'CNTY', ['upcase', ['to-string', ['get', 'agency']]]],
  ], '#eab308',
  // ORANGE: Unsure / everything else
  '#f97316',
];

const FEDERAL_LANDS_TILE_URL = 'https://tiles.arcgis.com/tiles/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Federal_Lands/VectorTileServer';

export default function LandAccessOverlay({ visible }: LandAccessOverlayProps) {
  const map = useMap();
  const layerRef = useRef<L.MaplibreGL | null>(null);

  useEffect(() => {
    if (!visible) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }

    // Create the MapLibre GL layer if it doesn't exist yet.
    if (!layerRef.current) {
      const glLayer = L.maplibreGL({
        style: {
          version: 8,
          sources: {
            padus: {
              type: 'vector',
              url: FEDERAL_LANDS_TILE_URL,
            },
          },
          layers: [
            {
              id: 'padus-fill',
              type: 'fill',
              source: 'padus',
              'source-layer': 'agbur',
              minzoom: MIN_ZOOM,
              paint: {
                'fill-color': FILL_COLOR_EXPR,
                'fill-opacity': 0.35,
              },
            },
            {
              id: 'padus-outline',
              type: 'line',
              source: 'padus',
              'source-layer': 'agbur',
              minzoom: MIN_ZOOM,
              paint: {
                'line-color': FILL_COLOR_EXPR,
                'line-opacity': 0.7,
                'line-width': 1,
              },
            },
          ],
        },
        // Suppress the MapLibre attribution control — Leaflet handles attribution.
        attributionControl: false,
      });

      glLayer.addTo(map);
      layerRef.current = glLayer;
    }

    return () => {
      // Cleanup on unmount only — visibility toggling is handled above.
    };
  }, [visible, map]);

  // Cleanup layer on unmount.
  useEffect(() => {
    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
