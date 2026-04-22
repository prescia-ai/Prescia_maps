import { useCallback, useEffect, useRef, useState } from 'react';
import { GeoJSON, useMap } from 'react-leaflet';
import type { FeatureCollection, Polygon, MultiPolygon } from 'geojson';

interface PADUSProperties {
  Mang_Name: string;
  GAP_Sts: number;
  Des_Tp: string;
  Unit_Nm?: string;
}

interface LandAccessOverlayProps {
  visible: boolean;
}

function getAccessColor(props: PADUSProperties): string {
  const mang = props.Mang_Name || '';
  const gap = props.GAP_Sts || 4;
  const designation = props.Des_Tp || '';

  // RED: Off Limits
  if (mang === 'NPS' || mang === 'FWS' || mang === 'DOD') return '#ef4444';
  if (designation.includes('WILDERNESS') || designation.includes('WILD AREA')) return '#ef4444';
  if (gap <= 2) return '#ef4444'; // High protection status

  // GREEN: Public OK
  if ((mang.includes('BLM') || mang.includes('USFS')) && gap === 3) return '#22c55e';
  if (mang === 'BOR') return '#22c55e'; // Bureau of Reclamation

  // YELLOW: State/Private - Permission Required
  if (mang.includes('STATE') || mang.includes('STAT')) return '#eab308';
  if (mang.includes('LOC') || mang.includes('CNTY')) return '#eab308';

  // ORANGE: Unsure
  return '#f97316';
}

function getAccessLabel(props: PADUSProperties): string {
  const color = getAccessColor(props);
  if (color === '#ef4444') return 'Off Limits';
  if (color === '#22c55e') return 'Public — OK to Detect';
  if (color === '#eab308') return 'Private — Permit Required';
  return 'Unsure — Verify First';
}

export default function LandAccessOverlay({ visible }: LandAccessOverlayProps) {
  const map = useMap();
  const [data, setData] = useState<FeatureCollection<Polygon | MultiPolygon, PADUSProperties> | null>(null);
  const fetchingRef = useRef(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchData = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    try {
      const bounds = map.getBounds();
      const bbox = [
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      ].join(',');

      // Use backend proxy to avoid CORS issues
      const url = new URL('/api/v1/land-access/pad-us-proxy', window.location.origin);
      url.searchParams.set('bbox', bbox);

      const response = await fetch(url.toString());
      if (!response.ok) {
        const bodySnippet = await response.text().then((t) => t.slice(0, 500)).catch(() => '');
        throw new Error(`HTTP ${response.status}: ${bodySnippet}`);
      }

      const geojson = await response.json();
      setData(geojson);
    } catch (error) {
      console.error('Failed to fetch PAD-US data:', error instanceof Error ? error.message : error);
      setData(null);
    } finally {
      fetchingRef.current = false;
    }
  }, [map]);

  const debouncedFetch = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchData, 400);
  }, [fetchData]);

  useEffect(() => {
    if (!visible) {
      setData(null);
      return;
    }

    fetchData();

    map.on('moveend', debouncedFetch);
    return () => {
      map.off('moveend', debouncedFetch);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [map, visible, fetchData, debouncedFetch]);

  if (!visible || !data) return null;

  return (
    <GeoJSON
      key={data.features?.length}
      data={data}
      style={(feature) => {
        if (!feature) return {};
        const color = getAccessColor(feature.properties as PADUSProperties);
        return {
          fillColor: color,
          fillOpacity: 0.35,
          color: color,
          weight: 1,
          opacity: 0.6,
        };
      }}
      onEachFeature={(feature, layer) => {
        const props = feature.properties as PADUSProperties;
        const label = getAccessLabel(props);
        const name = props.Unit_Nm || props.Mang_Name || 'Unknown';

        layer.bindPopup(`
          <div class="text-sm">
            <strong>${name}</strong><br/>
            <span class="text-xs text-gray-600">${label}</span><br/>
            <span class="text-xs text-gray-500">Managed by: ${props.Mang_Name || 'Unknown'}</span>
          </div>
        `);
      }}
    />
  );
}
