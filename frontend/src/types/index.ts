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
  // Personal layers
  my_hunts: boolean;
}

// ── User Hunt Pins ────────────────────────────────────────────────────────────

export interface UserPin {
  id: string;
  user_id: string;
  name: string;
  latitude: number;
  longitude: number;
  hunt_date: string;
  time_spent: string | null;
  notes: string | null;
  finds_count: number | null;
  privacy: 'public' | 'friends' | 'private';
  created_at: string;
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

// ── Community Pin Submissions ─────────────────────────────────────────────────

export interface PinSubmission {
  id: string;
  submitter_id: string;
  submitter_username: string | null;
  name: string;
  pin_type: string | null;
  suggested_type: string | null;
  latitude: number;
  longitude: number;
  date_era: string | null;
  description: string | null;
  source_reference: string | null;
  tags: string | null;
  status: 'pending' | 'approved' | 'rejected';
  admin_notes: string | null;
  rejection_reason: string | null;
  reviewed_at: string | null;
  submitted_at: string;
}

// ── Social Feed ───────────────────────────────────────────────────────────────

export type ReactionType = 'gold' | 'bullseye' | 'shovel' | 'fire';

export interface PostReactions {
  gold: number;
  bullseye: number;
  shovel: number;
  fire: number;
}

export interface Post {
  id: string;
  author_id: string;
  author_username: string | null;
  author_display_name: string | null;
  author_avatar_url?: string | null;
  content: string;
  privacy: 'public' | 'followers' | 'private';
  created_at: string;
  comment_count: number;
  reactions: PostReactions;
  my_reaction: ReactionType | null;
}

export interface Comment {
  id: string;
  post_id: string;
  author_id: string;
  author_username: string | null;
  author_display_name: string | null;
  author_avatar_url?: string | null;
  content: string;
  created_at: string;
}

export interface FollowInfo {
  user_id: string;
  username: string | null;
  display_name: string | null;
  avatar_url?: string | null;
}

export interface PublicProfile {
  id: string;
  username: string | null;
  display_name: string | null;
  bio: string | null;
  location: string | null;
  privacy: string;
  created_at: string | null;
  followers_count: number;
  following_count: number;
  is_following: boolean;
  avatar_url?: string | null;
}
