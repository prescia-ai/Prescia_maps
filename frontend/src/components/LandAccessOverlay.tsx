import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import * as maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import '@maplibre/maplibre-gl-leaflet';
import L from 'leaflet';

interface LandAccessOverlayProps {
  visible: boolean;
}

// Keep getAccessLabel exported in case other components use it.
export function getAccessLabel(mangName: string, gapSts: number, desTp: string): string {
  const mang = mangName || '';
  const gap = gapSts || 4;
  const designation = desTp || '';

  // RED: Off Limits
  if (mang === 'NPS' || mang === 'FWS' || mang === 'DOD') return 'Off Limits';
  if (designation.includes('WILDERNESS') || designation.includes('WILD AREA')) return 'Off Limits';
  if (gap <= 2) return 'Off Limits';

  // GREEN: Public OK
  if ((mang.includes('BLM') || mang.includes('USFS')) && gap === 3) return 'Public — OK to Detect';
  if (mang === 'BOR') return 'Public — OK to Detect';

  // YELLOW: State/Local
  if (mang.includes('STATE') || mang.includes('STAT')) return 'Private — Permit Required';
  if (mang.includes('LOC') || mang.includes('CNTY')) return 'Private — Permit Required';

  return 'Unsure — Verify First';
}

const MIN_ZOOM = 9;

// MapLibre fill-color expression that ports the getAccessColor logic.
const FILL_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  'case',
  // RED: NPS, FWS, DOD — always off-limits
  ['any',
    ['==', ['get', 'Mang_Name'], 'NPS'],
    ['==', ['get', 'Mang_Name'], 'FWS'],
    ['==', ['get', 'Mang_Name'], 'DOD'],
    ['in', 'WILDERNESS', ['upcase', ['to-string', ['get', 'Des_Tp']]]],
    ['in', 'WILD AREA', ['upcase', ['to-string', ['get', 'Des_Tp']]]],
    ['<=', ['to-number', ['get', 'GAP_Sts'], 4], 2],
  ], '#ef4444',
  // GREEN: BLM/USFS at GAP 3, or Bureau of Reclamation
  ['any',
    ['all',
      ['in', 'BLM', ['upcase', ['to-string', ['get', 'Mang_Name']]]],
      ['==', ['to-number', ['get', 'GAP_Sts'], 4], 3],
    ],
    ['all',
      ['in', 'USFS', ['upcase', ['to-string', ['get', 'Mang_Name']]]],
      ['==', ['to-number', ['get', 'GAP_Sts'], 4], 3],
    ],
    ['==', ['get', 'Mang_Name'], 'BOR'],
  ], '#22c55e',
  // YELLOW: State / local government land
  ['any',
    ['in', 'STATE', ['upcase', ['to-string', ['get', 'Mang_Name']]]],
    ['in', 'STAT', ['upcase', ['to-string', ['get', 'Mang_Name']]]],
    ['in', 'LOC', ['upcase', ['to-string', ['get', 'Mang_Name']]]],
    ['in', 'CNTY', ['upcase', ['to-string', ['get', 'Mang_Name']]]],
  ], '#eab308',
  // ORANGE: Unsure / everything else
  '#f97316',
];

const PMTILES_URL = '/api/v1/land-access/padus.pmtiles';

export default function LandAccessOverlay({ visible }: LandAccessOverlayProps) {
  const map = useMap();
  const layerRef = useRef<L.MaplibreGL | null>(null);
  const protocolRef = useRef<Protocol | null>(null);

  useEffect(() => {
    if (!visible) {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      return;
    }

    // Register the pmtiles:// protocol with MapLibre once.
    if (!protocolRef.current) {
      const protocol = new Protocol();
      maplibregl.addProtocol('pmtiles', protocol.tile.bind(protocol));
      protocolRef.current = protocol;
    }

    // Create the MapLibre GL layer if it doesn't exist yet.
    if (!layerRef.current) {
      const glLayer = L.maplibreGL({
        style: {
          version: 8,
          sources: {
            padus: {
              type: 'vector',
              url: `pmtiles://${PMTILES_URL}`,
            },
          },
          layers: [
            {
              id: 'padus-fill',
              type: 'fill',
              source: 'padus',
              'source-layer': 'padus',
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
              'source-layer': 'padus',
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

  // Cleanup protocol and layer on unmount.
  useEffect(() => {
    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
      if (protocolRef.current) {
        maplibregl.removeProtocol('pmtiles');
        protocolRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
