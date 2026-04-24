import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

interface LandAccessOverlayProps {
  visible: boolean;
}

function resolveAgencyRaw(props: Record<string, unknown>): string {
  return String(
    props?.agency ?? props?.Mang_Name ?? props?.manager ?? props?.AGBUR ?? props?.agbur ?? ''
  ).toUpperCase();
}

// Keep getAccessLabel exported in case other components use it.
export function getAccessLabel(props: Record<string, unknown> | string): string {
  const raw = typeof props === 'string' ? props.toUpperCase() : resolveAgencyRaw(props);

  // RED: Off Limits
  if (raw.includes('PARK') || raw.includes('NPS')) return 'Off Limits';
  if (raw.includes('WILDLIFE') || raw.includes('FWS') || raw.includes('FISH')) return 'Off Limits';
  if (raw.includes('DOD') || raw.includes('DEFENSE') || raw.includes('ARMY') || raw.includes('AIR FORCE') || raw.includes('NAVY') || raw.includes('MARINE')) return 'Off Limits';
  if (raw.includes('WILDERNESS')) return 'Off Limits';

  // GREEN: Public OK
  if (raw.includes('BLM') || raw.includes('BUREAU OF LAND')) return 'Public — OK to Detect';
  if (raw.includes('USFS') || raw.includes('FOREST SERVICE') || raw.includes('NATIONAL FOREST')) return 'Public — OK to Detect';
  if (raw.includes('BOR') || raw.includes('RECLAMATION')) return 'Public — OK to Detect';

  // YELLOW: State/Local
  if (raw.includes('STATE') || raw.includes('COUNTY') || raw.includes('CNTY') || raw.includes('LOCAL') || raw.includes('MUNICIPAL')) return 'Private — Permit Required';

  return 'Unsure — Verify First';
}

function getAccessColor(props: Record<string, unknown>): string {
  const raw = resolveAgencyRaw(props);

  // RED: off limits
  if (raw.includes('PARK') || raw.includes('NPS')) return '#ef4444';
  if (raw.includes('WILDLIFE') || raw.includes('FWS') || raw.includes('FISH')) return '#ef4444';
  if (raw.includes('DOD') || raw.includes('DEFENSE') || raw.includes('ARMY') || raw.includes('AIR FORCE') || raw.includes('NAVY') || raw.includes('MARINE')) return '#ef4444';
  if (raw.includes('WILDERNESS')) return '#ef4444';

  // GREEN: OK to detect
  if (raw.includes('BLM') || raw.includes('BUREAU OF LAND')) return '#22c55e';
  if (raw.includes('USFS') || raw.includes('FOREST SERVICE') || raw.includes('NATIONAL FOREST')) return '#22c55e';
  if (raw.includes('BOR') || raw.includes('RECLAMATION')) return '#22c55e';

  // YELLOW: permit required
  if (raw.includes('STATE') || raw.includes('COUNTY') || raw.includes('CNTY') || raw.includes('LOCAL') || raw.includes('MUNICIPAL')) return '#eab308';

  // ORANGE: unsure
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
      outFields: '*',
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

      if (data?.features?.length > 0) {
        console.log('LandAccessOverlay: first feature properties', data.features[0].properties);
      }

      removeLayer();
      layerRef.current = L.geoJSON(data, {
        style: (feature) => {
          const color = getAccessColor(feature?.properties ?? {});
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
