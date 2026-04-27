import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

interface LandAccessOverlayProps {
  visible: boolean;
}

// Keep getAccessLabel exported in case other components use it.
export function getAccessLabel(pubAccess: string): string {
  if (pubAccess === 'OA') return 'Public — OK to Detect';
  if (pubAccess === 'RA') return 'Private — Permit Required';
  if (pubAccess === 'XA') return 'Off Limits';
  return 'Unsure — Verify First';
}

function getAccessColor(pubAccess: string): string {
  if (pubAccess === 'OA') return '#22c55e';  // Open Access — green
  if (pubAccess === 'RA') return '#eab308';  // Restricted — yellow
  if (pubAccess === 'XA') return '#ef4444';  // Closed — red
  return '#f97316';                           // Unknown — orange
}

const MIN_ZOOM = 9;
// 2000 is the service max; larger pages mean fewer re-fetches after panning.
const RESULT_RECORD_COUNT = 2000;
const ESRI_URL = 'https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/PADUS_Public_Access/FeatureServer/0/query';
const DEBOUNCE_MS = 600;

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
      where: "Pub_Access='OA'",
      geometry: `${b.getWest()},${b.getSouth()},${b.getEast()},${b.getNorth()}`,
      geometryType: 'esriGeometryEnvelope',
      spatialRel: 'esriSpatialRelIntersects',
      inSR: '4326',
      outSR: '4326',
      outFields: 'Pub_Access,MngNm_Desc,Unit_Nm',
      returnGeometry: 'true',
      maxAllowableOffset: '0.001',
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
        interactive: false,
        style: (feature) => {
          const pubAccess: string = feature?.properties?.Pub_Access ?? '';
          const color = getAccessColor(pubAccess);
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
