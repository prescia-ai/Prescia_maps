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
  // Point feature types
  battle: boolean;
  town: boolean;
  mine: boolean;
  camp: boolean;
  railroad_stop: boolean;
  stagecoach_stop: boolean;
  trail: boolean;
  structure: boolean;
  church: boolean;
  cemetery: boolean;
  ferry: boolean;
  fairground: boolean;
  school: boolean;
  spring: boolean;
  locale: boolean;
  mission: boolean;
  trading_post: boolean;
  shipwreck: boolean;
  pony_express: boolean;
  abandoned_church: boolean;
  historic_brothel: boolean;
  // Linear feature types
  railroad: boolean;
  road: boolean;
  // Special layers
  heatmap: boolean;
  blm: boolean;
}

// ── Land Access ──────────────────────────────────────────────────────────────

export type LandAccessStatus = 'allowed' | 'off_limits' | 'private_permit' | 'unsure';

export interface LandAccessResponse {
  area_code: string;
  unit_name: string | null;
  managing_agency: string | null;
  designation: string | null;
  state: string | null;
  gap_status: number | null;
  status: LandAccessStatus;
  confidence: number;
  reason: string | null;
  source: string; // 'rule_tier1' | 'cached' | 'user_override'
  last_verified: string | null;
}

export interface LandAccessOverrideCreate {
  status: 'allowed' | 'off_limits';
  notes?: string;
}

export interface LandAccessOverrideResponse {
  area_code: string;
  status: string;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// ── Import ───────────────────────────────────────────────────────────────────

export interface ImportSummaryResponse {
  inserted: number;
  skipped_duplicate: number;
  skipped_invalid: number;
  errors: string[];
}
