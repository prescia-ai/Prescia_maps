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
  detecting_weight?: number | null; // 0–100
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
  raw_score?: number;
  breakdown: ScoreBreakdown;
  nearby_count: number;
  lat: number;
  lon: number;
  accessible?: string | null;
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
  cemetery: boolean;
  ferry: boolean;
  fairground: boolean;
  abandoned_fairground: boolean;
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
  aerials_1955: boolean;
  // Personal layers
  my_hunts: boolean;
  group_events: boolean;
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
  images?: Array<{ id: string; url: string; position: number }>;
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
  images?: Array<{ id: string; url: string; position: number }>;
  group_id?: string | null;
  group_name?: string | null;
  group_slug?: string | null;
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
  is_admin?: boolean;
  contributed_pins_count?: number;
}

export interface CollectionPhoto {
  id: string;
  user_id: string;
  url: string;
  caption: string | null;
  find_type: string | null;
  material: string | null;
  created_at: string;
}

// ── Badges ───────────────────────────────────────────────────────────────────

export type BadgeCategory = 'hunt_milestone' | 'finds' | 'sites' | 'score' | 'community' | 'social' | 'geographic' | 'treasure_trove';
export type BadgeRarity = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary';

export interface Badge {
  id: string;
  badge_id: string;
  name: string;
  description: string;
  category: BadgeCategory;
  criteria: Record<string, unknown>;
  points: number;
  rarity: BadgeRarity;
  image_url: string;
  created_at: string | null;
}

export interface BadgeProgress {
  badge: Badge;
  earned: boolean;
  earned_at: string | null;
  current_value: number;
  threshold: number | null;
  progress_pct: number;
}

export interface NewlyEarnedBadgesResponse {
  newly_earned: Badge[];
  total_earned: number;
}

// ── Groups ────────────────────────────────────────────────────────────────────

export interface Group {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  privacy: 'public' | 'private';
  created_by: string;
  created_at: string;
  updated_at: string | null;
  member_count: number;
  is_member: boolean;
  user_role: 'owner' | 'moderator' | 'member' | null;
  pending_request: boolean;
}

export interface GroupMember {
  user_id: string;
  username: string | null;
  display_name: string | null;
  avatar_url: string | null;
  role: 'owner' | 'moderator' | 'member';
  joined_at: string;
}

export interface GroupSearchResult {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  privacy: 'public' | 'private';
  member_count: number;
}

// ── Group Events ──────────────────────────────────────────────────────────────

export interface GroupEvent {
  id: string;
  group_id: string;
  group_name: string | null;
  group_slug: string | null;
  created_by: string;
  created_by_username: string | null;
  name: string;
  description: string | null;
  latitude: number;
  longitude: number;
  event_date: string;
  event_end_date: string | null;
  created_at: string;
  updated_at: string | null;
  rsvp_count: number;
  user_has_rsvpd: boolean;
}

export interface EventPin {
  id: string;
  group_id: string;
  group_name: string;
  group_slug: string;
  name: string;
  latitude: number;
  longitude: number;
  event_date: string;
  event_end_date: string | null;
  rsvp_count: number;
  user_has_rsvpd: boolean;
}

// ── Notifications ─────────────────────────────────────────────────────────────

export type NotificationType =
  | 'post_like'
  | 'post_comment'
  | 'submission_approved'
  | 'badge_earned'
  | 'group_invite'
  | 'group_join'
  | string;

export interface Notification {
  id: string;
  type: NotificationType;
  user_id: string;
  actor_id: string | null;
  actor_username: string | null;
  actor_display_name: string | null;
  actor_avatar_url: string | null;
  ref_id: string | null;
  message: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  unread_count: number;
  notifications: Notification[];
}
