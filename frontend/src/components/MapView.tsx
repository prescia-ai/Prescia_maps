import { useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Popup,
  useMapEvents,
} from 'react-leaflet';
import type { LeafletMouseEvent } from 'leaflet';
import type {
  LocationFeature,
  LocationType,
  LayerState,
  HeatmapPoint,
} from '../types';
import type { Feature, Geometry, LineString, MultiLineString } from 'geojson';
import type { LinearProperties } from '../types';
import HeatmapLayer from './HeatmapLayer';

// ── Colour helpers ────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  battle:          '#ef4444', // red
  town:            '#3b82f6', // blue
  mine:            '#f59e0b', // amber
  camp:            '#22c55e', // green
  railroad_stop:   '#a855f7', // purple
  trail:           '#14b8a6', // teal
  structure:       '#f97316', // orange
  church:          '#ec4899', // pink
  cemetery:        '#6366f1', // indigo
  ferry:           '#06b6d4', // cyan
  stagecoach_stop: '#84cc16', // lime
  fairground:      '#eab308', // yellow
  school:          '#8b5cf6', // violet
  spring:          '#10b981', // emerald
  locale:          '#94a3b8', // slate
  event:           '#94a3b8', // slate
  mission:         '#d97706', // amber-dark
  trading_post:    '#b45309', // brown-amber
  shipwreck:       '#0369a1', // dark blue
  pony_express:    '#dc2626', // dark red
};

function markerColor(type: LocationType): string {
  return TYPE_COLORS[type] ?? '#94a3b8'; // slate fallback
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ClickHandler({ onClick }: { onClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e: LeafletMouseEvent) {
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function LocationMarkers({
  features,
  layers,
  onSelect,
}: {
  features: LocationFeature[];
  layers: LayerState;
  onSelect: (f: LocationFeature) => void;
}) {
  return (
    <>
      {features.map((f) => {
        const [lng, lat] = f.geometry.coordinates;
        const { type, name, year, description, confidence } = f.properties;

        // Filter by layer
        const MINES_TYPES = new Set(['mine', 'camp', 'spring']);
        const TRAILS_TYPES = new Set(['trail', 'stagecoach_stop', 'ferry', 'pony_express']);

        if (MINES_TYPES.has(type)) {
          if (!layers.mines) return null;
        } else if (TRAILS_TYPES.has(type)) {
          if (!layers.trails) return null;
        } else if (!layers.events) {
          return null;
        }

        const color = markerColor(type);

        return (
          <CircleMarker
            key={String(f.properties.id)}
            center={[lat, lng]}
            radius={7}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: 0.75,
              weight: 1.5,
            }}
            eventHandlers={{
              click: () => onSelect(f),
            }}
          >
            <Popup>
              <div className="min-w-[180px]">
                <strong className="block text-sm">{name}</strong>
                {year != null && <span className="text-xs text-gray-500">c. {year}</span>}
                {description && <p className="text-xs mt-1">{description}</p>}
                {confidence != null && (
                  <p className="text-xs text-gray-400 mt-1">
                    Confidence: {Math.round(confidence * 100)}%
                  </p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}

function LinearFeatures({
  features,
  layers,
}: {
  features: Feature<Geometry, LinearProperties>[];
  layers: LayerState;
}) {
  return (
    <>
      {features.map((f) => {
        const { type, id } = f.properties;

        if (type === 'railroad' && !layers.railroads) return null;
        if (type === 'trail' && !layers.trails) return null;
        // unknown types respect railroads toggle
        if (type !== 'railroad' && type !== 'trail' && !layers.railroads) return null;

        const isRailroad = type === 'railroad';
        const color = isRailroad ? '#ef4444' : '#22c55e';
        const dashArray = isRailroad ? undefined : '8 6';

        // Flatten LineString / MultiLineString into position arrays
        const geom = f.geometry;
        const lines: [number, number][][] = [];

        if (geom.type === 'LineString') {
          lines.push(
            (geom as LineString).coordinates.map(([lng, lat]) => [lat, lng]),
          );
        } else if (geom.type === 'MultiLineString') {
          (geom as MultiLineString).coordinates.forEach((segment) => {
            lines.push(segment.map(([lng, lat]) => [lat, lng]));
          });
        }

        return lines.map((positions, idx) => (
          <Polyline
            key={`${String(id)}-${idx}`}
            positions={positions}
            pathOptions={{ color, weight: isRailroad ? 2.5 : 2, dashArray, opacity: 0.8 }}
          >
            <Popup>
              <span className="text-sm font-medium">{f.properties.name}</span>
              <span className="block text-xs text-gray-500 capitalize">{type}</span>
            </Popup>
          </Polyline>
        ));
      })}
    </>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface MapViewProps {
  locations: LocationFeature[];
  linearFeatures: Feature<Geometry, LinearProperties>[];
  heatmapPoints: HeatmapPoint[];
  layers: LayerState;
  onMapClick: (lat: number, lon: number) => void;
  onLocationSelect: (f: LocationFeature) => void;
  onLandAccessClick?: (lat: number, lon: number) => void;
}

export default function MapView({
  locations,
  linearFeatures,
  heatmapPoints,
  layers,
  onMapClick,
  onLocationSelect,
  onLandAccessClick,
}: MapViewProps) {
  const handleClick = useCallback(
    (lat: number, lon: number) => {
      if (layers.blm && onLandAccessClick) {
        onLandAccessClick(lat, lon);
      }
      onMapClick(lat, lon);
    },
    [onMapClick, layers.blm, onLandAccessClick],
  );

  return (
    <MapContainer
      center={[39.5, -98.35]}
      zoom={5}
      className="w-full h-full"
      zoomControl={true}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
      />

      {/* PAD-US land access overlay */}
      {layers.blm && (
        <TileLayer
          url="https://gis.usgs.gov/arcgis/rest/services/PADUS3_0/MapServer/tile/{z}/{y}/{x}"
          attribution="USGS PAD-US 3.0"
          opacity={0.4}
          zIndex={5}
        />
      )}

      <ClickHandler onClick={handleClick} />

      <LocationMarkers
        features={locations}
        layers={layers}
        onSelect={onLocationSelect}
      />

      <LinearFeatures features={linearFeatures} layers={layers} />

      {heatmapPoints.length > 0 && (
        <HeatmapLayer points={heatmapPoints} visible={layers.heatmap} />
      )}
    </MapContainer>
  );
}
