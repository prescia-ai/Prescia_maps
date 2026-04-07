import type { Feature, FeatureCollection, Point, LineString, MultiLineString, Geometry } from 'geojson';

// ── Location / point features ────────────────────────────────────────────────

export type LocationType =
  | 'battle'
  | 'town'
  | 'mine'
  | 'camp'
  | 'railroad_stop'
  | 'trail'
  | string; // allow unknown types from the API

export interface LocationProperties {
  id: string | number;
  name: string;
  type: LocationType;
  year?: number | string | null;
  description?: string | null;
  source?: string | null;
  confidence?: number | null; // 0–1
}

export type LocationFeature = Feature<Point, LocationProperties>;

export interface LocationFeatureCollection extends FeatureCollection<Point, LocationProperties> {
  features: LocationFeature[];
}

// ── Linear features (trails, railroads) ─────────────────────────────────────

export interface LinearProperties {
  id: string | number;
  name: string;
  type: 'trail' | 'railroad' | string;
  source?: string | null;
}

export type LinearFeature = Feature<LineString | MultiLineString, LinearProperties>;

export interface LinearFeatureCollection extends FeatureCollection<Geometry, LinearProperties> {
  features: Feature<Geometry, LinearProperties>[];
}

// ── Heatmap ──────────────────────────────────────────────────────────────────

export interface HeatmapPoint {
  lat: number;
  lon: number;
  weight: number;
}

// ── Score ────────────────────────────────────────────────────────────────────

export interface ScoreBreakdown {
  [component: string]: number;
}

export interface ScoreResponse {
  score: number;
  breakdown: ScoreBreakdown;
  lat: number;
  lon: number;
}

// ── Layer visibility state ───────────────────────────────────────────────────

export interface LayerState {
  events: boolean;
  railroads: boolean;
  trails: boolean;
  mines: boolean;
  heatmap: boolean;
  blm: boolean;
}
