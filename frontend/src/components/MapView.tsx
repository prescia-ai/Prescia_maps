import { useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Popup,
  useMapEvents,
  ZoomControl,
} from 'react-leaflet';
import type { LeafletMouseEvent } from 'leaflet';
import type {
  LocationFeature,
  LocationType,
  LayerState,
  HeatmapPoint,
  UserPin,
  EventPin,
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
  abandoned_church: '#ec4899', // pink (same family as church)
  abandoned_fairground: '#d97706', // amber/brown
  historic_brothel: '#f43f5e', // rose
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

function ContextMenuHandler({ onContextMenu }: { onContextMenu: (lat: number, lon: number) => void }) {
  useMapEvents({
    contextmenu(e: LeafletMouseEvent) {
      e.originalEvent.preventDefault();
      onContextMenu(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function UserPinMarkers({ pins }: { pins: UserPin[] }) {
  if (!pins.length) return null;
  return (
    <>
      {pins.map((pin) => {
        const dateLabel = pin.hunt_date
          ? new Date(pin.hunt_date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
          : null;
        return (
          <CircleMarker
            key={pin.id}
            center={[pin.latitude, pin.longitude]}
            radius={8}
            pathOptions={{
              color: '#ffffff',
              fillColor: '#10b981',
              fillOpacity: 0.9,
              weight: 2,
            }}
          >
            <Popup>
              <div className="min-w-[180px]">
                <strong className="block text-sm">{pin.name}</strong>
                {dateLabel && <span className="text-xs text-gray-500">{dateLabel}</span>}
                {pin.time_spent && (
                  <p className="text-xs text-gray-600 mt-0.5">⏱ {pin.time_spent}</p>
                )}
                {pin.finds_count != null && (
                  <p className="text-xs text-gray-600 mt-0.5">🪙 {pin.finds_count} find{pin.finds_count !== 1 ? 's' : ''}</p>
                )}
                {pin.notes && <p className="text-xs mt-1 text-gray-700">{pin.notes}</p>}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
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

        // Filter by layer — check if this specific type has a per-type toggle.
        // If the type isn't in LayerState (unknown type), show it by default.
        if (type in layers && !layers[type as keyof LayerState]) return null;

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

        if (type in layers && !layers[type as keyof LayerState]) return null;

        const LINEAR_COLORS: Record<string, { color: string; dashArray?: string; weight: number }> = {
          railroad: { color: '#ef4444', weight: 2.5 },
          trail:    { color: '#22c55e', weight: 2, dashArray: '8 6' },
          road:     { color: '#d97706', weight: 2, dashArray: '6 4' },
          water:    { color: '#06b6d4', weight: 2, dashArray: '4 4' },
        };
        const lineStyle = LINEAR_COLORS[type] ?? { color: '#94a3b8', weight: 2, dashArray: '4 4' };
        const { color, dashArray, weight } = lineStyle;

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
            pathOptions={{ color, weight, dashArray, opacity: 0.8 }}
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

function EventPinMarkers({ pins }: { pins: EventPin[] }) {
  if (!pins.length) return null;
  return (
    <>
      {pins.map((pin) => {
        const dateLabel = pin.event_date
          ? new Date(pin.event_date).toLocaleDateString('en-US', {
              weekday: 'short',
              year: 'numeric',
              month: 'short',
              day: 'numeric',
              hour: 'numeric',
              minute: '2-digit',
            })
          : null;
        const endDateLabel = pin.event_end_date
          ? new Date(pin.event_end_date).toLocaleTimeString('en-US', {
              hour: 'numeric',
              minute: '2-digit',
            })
          : null;
        return (
          <CircleMarker
            key={pin.id}
            center={[pin.latitude, pin.longitude]}
            radius={10}
            pathOptions={{
              color: '#ffffff',
              fillColor: '#8b5cf6',
              fillOpacity: 0.9,
              weight: 2,
            }}
          >
            <Popup>
              <div className="min-w-[180px]">
                <strong className="block text-sm font-semibold">{pin.name}</strong>
                <span className="text-xs text-gray-500">in {pin.group_name}</span>
                {dateLabel && (
                  <p className="text-xs text-gray-600 mt-1">{dateLabel}</p>
                )}
                {endDateLabel && (
                  <p className="text-xs text-gray-600">until {endDateLabel}</p>
                )}
                <p className="text-xs text-gray-600 mt-0.5">{pin.rsvp_count} going</p>
                {pin.user_has_rsvpd && (
                  <p className="text-xs text-green-600 mt-0.5">✓ You're going</p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}

interface MapViewProps {
  locations: LocationFeature[];
  linearFeatures: Feature<Geometry, LinearProperties>[];
  heatmapPoints: HeatmapPoint[];
  layers: LayerState;
  onMapClick: (lat: number, lon: number) => void;
  onLocationSelect: (f: LocationFeature) => void;
  onLandAccessClick?: (lat: number, lon: number) => void;
  onContextMenu?: (lat: number, lon: number) => void;
  userPins?: UserPin[];
  eventPins?: EventPin[];
}

export default function MapView({
  locations,
  linearFeatures,
  heatmapPoints,
  layers,
  onMapClick,
  onLocationSelect,
  onLandAccessClick,
  onContextMenu,
  userPins,
  eventPins,
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
      zoomControl={false}
    >
      <ZoomControl position="bottomright" />
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
      />

      {/* PAD-US land access overlay */}
      {layers.blm && (
        <TileLayer
          url="https://gis.usgs.gov/arcgis/rest/services/PADUS3_0GAP_Status_Code/MapServer/tile/{z}/{y}/{x}"
          attribution="USGS PAD-US 3.0"
          opacity={0.4}
          zIndex={5}
        />
      )}

      <ClickHandler onClick={handleClick} />

      {onContextMenu && <ContextMenuHandler onContextMenu={onContextMenu} />}

      <LocationMarkers
        features={locations}
        layers={layers}
        onSelect={onLocationSelect}
      />

      <LinearFeatures features={linearFeatures} layers={layers} />

      {heatmapPoints.length > 0 && (
        <HeatmapLayer points={heatmapPoints} visible={layers.heatmap} />
      )}

      {userPins && userPins.length > 0 && (
        <UserPinMarkers pins={userPins} />
      )}

      {eventPins && eventPins.length > 0 && (
        <EventPinMarkers pins={eventPins} />
      )}
    </MapContainer>
  );
}
