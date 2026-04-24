import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
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

function getAccessColor(agency: string): string {
  const ag = (agency || '').toUpperCase();
  if (ag === 'NPS' || ag === 'FWS' || ag === 'DOD') return '#ef4444';
  if (ag === 'BLM' || ag === 'USFS' || ag === 'BOR') return '#22c55e';
  if (ag.includes('STATE') || ag.includes('STAT') || ag.includes('LOC') || ag.includes('CNTY')) return '#eab308';
  return '#f97316';
}

const MIN_ZOOM = 9;
// 500 is the max page size; at zoom ≥ 9 the viewport is small enough that this covers the area.
const RESULT_RECORD_COUNT = 500;
const ESRI_URL = 'https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Federal_Lands/FeatureServer/0/query';
const DEBOUNCE_MS = 300;

export default function LandAccessOverlay({ visible }: LandAccessOverlayProps) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function removeLayer() {
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
    }
  }

  async function fetchAndRender() {
    if (!visible || map.getZoom() < MIN_ZOOM) {
      removeLayer();
      return;
    }

    const b = map.getBounds();
    const params = new URLSearchParams({
      geometry: `${b.getWest()},${b.getSouth()},${b.getEast()},${b.getNorth()}`,
      geometryType: 'esriGeometryEnvelope',
      inSR: '4326',
      outSR: '4326',
      outFields: 'agency',
      returnGeometry: 'true',
      f: 'geojson',
      resultRecordCount: String(RESULT_RECORD_COUNT),
    });

    try {
      const res = await fetch(`${ESRI_URL}?${params}`);
      if (!res.ok) {
        console.warn(`LandAccessOverlay: Esri request failed (${res.status})`);
        return;
      }
      const data = await res.json();

      removeLayer();
      layerRef.current = L.geoJSON(data, {
        style: (feature) => {
          const agency: string = feature?.properties?.agency ?? '';
          const color = getAccessColor(agency);
          return { fillColor: color, fillOpacity: 0.35, color, weight: 1, opacity: 0.7 };
        },
      }).addTo(map);
    } catch (err) {
      console.warn('LandAccessOverlay: fetch error', err);
    }
  }

  function scheduleFetch() {
    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { fetchAndRender(); }, DEBOUNCE_MS);
  }

  useEffect(() => {
    if (!visible) {
      removeLayer();
      return;
    }

    map.on('moveend zoomend', scheduleFetch);
    fetchAndRender();

    return () => {
      map.off('moveend zoomend', scheduleFetch);
      if (debounceRef.current !== null) clearTimeout(debounceRef.current);
      removeLayer();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, map]);

  return null;
}
