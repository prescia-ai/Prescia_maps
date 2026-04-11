import axios from 'axios';
import { supabase } from '../lib/supabase';
import type {
  LocationFeatureCollection,
  LinearFeatureCollection,
  HeatmapPoint,
  ScoreResponse,
  LandAccessResponse,
  LandAccessOverrideCreate,
  LandAccessOverrideResponse,
  ImportSummaryResponse,
  UserPin,
  PinSubmission,
  Post,
  Comment,
  ReactionType,
  FollowInfo,
  PublicProfile,
  CollectionPhoto,
} from '../types';

// Minimal request payload types for pin operations
interface UserPinCreate {
  name: string;
  latitude: number;
  longitude: number;
  hunt_date: string;
  time_spent?: string | null;
  notes?: string | null;
  finds_count?: number | null;
  privacy?: 'public' | 'friends' | 'private';
}

interface UserPinUpdate {
  name?: string;
  latitude?: number;
  longitude?: number;
  hunt_date?: string;
  time_spent?: string | null;
  notes?: string | null;
  finds_count?: number | null;
  privacy?: 'public' | 'friends' | 'private';
}

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15_000,
});

// Attach Supabase access token to every request when a session exists
api.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    config.headers = config.headers ?? {};
    config.headers['Authorization'] = `Bearer ${session.access_token}`;
  }
  return config;
});

export async function fetchLocations(): Promise<LocationFeatureCollection> {
  const { data } = await api.get<LocationFeatureCollection>('/locations', {
    params: { per_type_limit: 2000 },
  });
  return data;
}

export async function fetchFeatures(): Promise<LinearFeatureCollection> {
  const { data } = await api.get<LinearFeatureCollection>('/features');
  return data;
}

export async function fetchHeatmap(): Promise<HeatmapPoint[]> {
  const { data } = await api.get<HeatmapPoint[]>('/heatmap');
  return data;
}

export async function fetchScore(lat: number, lon: number): Promise<ScoreResponse> {
  const { data } = await api.get<ScoreResponse>('/score', {
    params: { lat, lon },
  });
  return data;
}

export async function fetchBlmTileUrl(): Promise<{ url: string; attribution: string }> {
  const { data } = await api.get<{ url: string; attribution: string }>('/blm-lands/tile-url');
  return data;
}

export async function fetchLandAccess(lat: number, lon: number): Promise<LandAccessResponse> {
  const { data } = await api.get<LandAccessResponse>('/land-access', {
    params: { lat, lon },
  });
  return data;
}

export async function putLandAccessOverride(
  areaCode: string,
  payload: LandAccessOverrideCreate,
): Promise<LandAccessResponse> {
  const { data } = await api.put<LandAccessResponse>(
    `/land-access/${encodeURIComponent(areaCode)}/override`,
    payload,
  );
  return data;
}

export async function deleteLandAccessOverride(areaCode: string): Promise<void> {
  await api.delete(`/land-access/${encodeURIComponent(areaCode)}/override`);
}

export async function fetchLandAccessOverrides(): Promise<LandAccessOverrideResponse[]> {
  const { data } = await api.get<LandAccessOverrideResponse[]>('/land-access/overrides');
  return data;
}

export async function importLocations(data: any[]): Promise<ImportSummaryResponse> {
  const { data: result } = await api.post<ImportSummaryResponse>('/import/locations', data);
  return result;
}

export async function importFeatures(data: any): Promise<ImportSummaryResponse> {
  const { data: result } = await api.post<ImportSummaryResponse>('/import/features', data);
  return result;
}

export async function fetchMyPins(limit = 50, offset = 0): Promise<{ pins: UserPin[]; total: number }> {
  const { data } = await api.get<{ pins: UserPin[]; total: number }>('/pins/me', { params: { limit, offset } });
  return data;
}

export async function fetchUserPins(username: string, limit = 50, offset = 0): Promise<{ pins: UserPin[]; total: number }> {
  const { data } = await api.get<{ pins: UserPin[]; total: number }>(`/pins/user/${encodeURIComponent(username)}`, { params: { limit, offset } });
  return data;
}

export async function createPin(data: UserPinCreate): Promise<UserPin> {
  const { data: result } = await api.post<UserPin>('/pins', data);
  return result;
}

export async function updatePin(id: string, data: UserPinUpdate): Promise<UserPin> {
  const { data: result } = await api.put<UserPin>(`/pins/${id}`, data);
  return result;
}

export async function deletePin(id: string): Promise<void> {
  await api.delete(`/pins/${id}`);
}

// ── Community Pin Submissions ─────────────────────────────────────────────────

interface PinSubmissionCreate {
  name: string;
  pin_type?: string | null;
  suggested_type?: string | null;
  latitude: number;
  longitude: number;
  date_era?: string | null;
  description?: string | null;
  source_reference?: string | null;
  tags?: string | null;
}

interface PinSubmissionAdminUpdate {
  name?: string;
  pin_type?: string | null;
  suggested_type?: string | null;
  latitude?: number;
  longitude?: number;
  date_era?: string | null;
  description?: string | null;
  source_reference?: string | null;
  tags?: string | null;
  admin_notes?: string | null;
  rejection_reason?: string | null;
  status?: 'pending' | 'approved' | 'rejected';
}

export async function createSubmission(data: PinSubmissionCreate): Promise<PinSubmission> {
  const { data: result } = await api.post<PinSubmission>('/submissions', data);
  return result;
}

export async function fetchMySubmissions(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<{ submissions: PinSubmission[]; total: number }> {
  const { data } = await api.get<{ submissions: PinSubmission[]; total: number }>(
    '/submissions/me',
    { params: { status, limit, offset } },
  );
  return data;
}

export async function fetchAdminSubmissions(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<{ submissions: PinSubmission[]; total: number }> {
  const { data } = await api.get<{ submissions: PinSubmission[]; total: number }>(
    '/admin/submissions',
    { params: { status, limit, offset } },
  );
  return data;
}

export async function fetchAdminSubmission(id: string): Promise<PinSubmission> {
  const { data } = await api.get<PinSubmission>(`/admin/submissions/${id}`);
  return data;
}

export async function updateAdminSubmission(
  id: string,
  data: PinSubmissionAdminUpdate,
): Promise<PinSubmission> {
  const { data: result } = await api.put<PinSubmission>(`/admin/submissions/${id}`, data);
  return result;
}

export async function exportApprovedSubmissions(): Promise<void> {
  const response = await api.get('/admin/submissions/export', { responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'community_pins_export.json');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

// ── Social Feed ───────────────────────────────────────────────────────────────

export async function createPost(
  content: string,
  privacy: 'public' | 'followers' | 'private' = 'public',
  group_id?: string | null,
): Promise<Post> {
  const { data } = await api.post<Post>('/posts', { content, privacy, group_id: group_id ?? null });
  return data;
}

export async function fetchGlobalFeed(
  limit = 20,
  offset = 0,
): Promise<{ posts: Post[]; total: number }> {
  const { data } = await api.get<{ posts: Post[]; total: number }>('/feed', {
    params: { limit, offset },
  });
  return data;
}

export async function fetchHomeFeed(
  limit = 20,
  offset = 0,
): Promise<{ posts: Post[]; total: number }> {
  const { data } = await api.get<{ posts: Post[]; total: number }>('/feed/home', {
    params: { limit, offset },
  });
  return data;
}

export async function deletePost(postId: string): Promise<void> {
  await api.delete(`/posts/${postId}`);
}

export async function fetchComments(
  postId: string,
  limit = 50,
  offset = 0,
): Promise<{ comments: Comment[]; total: number }> {
  const { data } = await api.get<{ comments: Comment[]; total: number }>(
    `/posts/${postId}/comments`,
    { params: { limit, offset } },
  );
  return data;
}

export async function createComment(postId: string, content: string): Promise<Comment> {
  const { data } = await api.post<Comment>(`/posts/${postId}/comments`, { content });
  return data;
}

export async function deleteComment(postId: string, commentId: string): Promise<void> {
  await api.delete(`/posts/${postId}/comments/${commentId}`);
}

export async function reactToPost(postId: string, reactionType: ReactionType): Promise<Post> {
  const { data } = await api.put<Post>(`/posts/${postId}/react`, {
    reaction_type: reactionType,
  });
  return data;
}

// ── Follow System ─────────────────────────────────────────────────────────────

export async function followUser(username: string): Promise<void> {
  await api.post(`/users/${encodeURIComponent(username)}/follow`);
}

export async function unfollowUser(username: string): Promise<void> {
  await api.delete(`/users/${encodeURIComponent(username)}/follow`);
}

export async function fetchFollowers(
  username: string,
  limit = 50,
  offset = 0,
): Promise<{ users: FollowInfo[]; total: number }> {
  const { data } = await api.get<{ users: FollowInfo[]; total: number }>(
    `/users/${encodeURIComponent(username)}/followers`,
    { params: { limit, offset } },
  );
  return data;
}

export async function fetchFollowing(
  username: string,
  limit = 50,
  offset = 0,
): Promise<{ users: FollowInfo[]; total: number }> {
  const { data } = await api.get<{ users: FollowInfo[]; total: number }>(
    `/users/${encodeURIComponent(username)}/following`,
    { params: { limit, offset } },
  );
  return data;
}

export async function fetchUserPosts(
  username: string,
  limit = 20,
  offset = 0,
): Promise<{ posts: Post[]; total: number }> {
  const { data } = await api.get<{ posts: Post[]; total: number }>(
    `/posts/user/${encodeURIComponent(username)}`,
    { params: { limit, offset } },
  );
  return data;
}

export async function fetchGroupPosts(
  groupId: string,
  limit = 20,
  offset = 0,
): Promise<{ posts: Post[]; total: number }> {
  const { data } = await api.get<{ posts: Post[]; total: number }>(
    `/posts/group/${groupId}`,
    { params: { limit, offset } },
  );
  return data;
}

export async function fetchPublicProfile(username: string): Promise<PublicProfile> {
  const { data } = await api.get<PublicProfile>(`/auth/profile/${encodeURIComponent(username)}`);
  return data;
}

export async function fetchGoogleAuthUrl(): Promise<string> {
  const { data } = await api.get<{ url: string }>('/google/auth-url');
  return data.url;
}

export async function fetchGoogleStatus(): Promise<{
  connected: boolean;
  google_email: string | null;
  connected_at: string | null;
  has_folder: boolean;
}> {
  const { data } = await api.get('/google/status');
  return data;
}

export async function disconnectGoogle(): Promise<void> {
  await api.post('/google/disconnect');
}

export async function uploadAvatar(file: File): Promise<{ avatar_url: string; file_id: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<{ avatar_url: string; file_id: string }>(
    '/google/upload-avatar',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 30_000 },
  );
  return data;
}

export async function deleteAvatar(): Promise<void> {
  await api.delete('/google/avatar');
}

export async function uploadPostImages(
  postId: string,
  files: File[],
): Promise<{ images: Array<{ id: string; url: string; position: number }> }> {
  const formData = new FormData();
  formData.append('post_id', postId);
  for (const file of files) {
    formData.append('files', file);
  }
  const { data } = await api.post<{ images: Array<{ id: string; url: string; position: number }> }>(
    '/google/upload-post-images',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60_000 },
  );
  return data;
}

export async function deletePostImages(postId: string): Promise<{ status: string; count: number }> {
  const { data } = await api.delete<{ status: string; count: number }>(`/google/post-images/${postId}`);
  return data;
}

export async function uploadPinImages(
  pinId: string,
  files: File[],
  addToCollection: boolean = false,
): Promise<{ images: Array<{ id: string; url: string; position: number }> }> {
  const formData = new FormData();
  formData.append('pin_id', pinId);
  if (addToCollection) {
    formData.append('add_to_collection', 'true');
  }
  for (const file of files) {
    formData.append('files', file);
  }
  const { data } = await api.post<{ images: Array<{ id: string; url: string; position: number }> }>(
    '/google/upload-pin-images',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60_000 },
  );
  return data;
}

export async function deletePinImages(pinId: string): Promise<{ status: string; count: number }> {
  const { data } = await api.delete<{ status: string; count: number }>(`/google/pin-images/${pinId}`);
  return data;
}

// ── Collection ─────────────────────────────────────────────────────────────────

export async function fetchCollection(
  username: string,
  limit = 30,
  offset = 0,
): Promise<{ photos: CollectionPhoto[]; total: number }> {
  const { data } = await api.get<{ photos: CollectionPhoto[]; total: number }>(
    `/collection/${encodeURIComponent(username)}`,
    { params: { limit, offset } },
  );
  return data;
}

export async function uploadCollectionPhoto(
  file: File,
  caption?: string,
): Promise<CollectionPhoto> {
  const formData = new FormData();
  formData.append('file', file);
  if (caption) {
    formData.append('caption', caption);
  }
  const { data } = await api.post<CollectionPhoto>(
    '/collection',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60_000 },
  );
  return data;
}

export async function updateCollectionPhoto(
  photoId: string,
  caption: string | null,
): Promise<CollectionPhoto> {
  const { data } = await api.put<CollectionPhoto>(
    `/collection/${photoId}`,
    { caption },
  );
  return data;
}

export async function deleteCollectionPhoto(photoId: string): Promise<void> {
  await api.delete(`/collection/${photoId}`);
}

export async function deleteAccount(): Promise<void> {
  await api.delete('/auth/account');
}

export async function searchUsers(
  query: string,
): Promise<Array<{ username: string; display_name: string | null; avatar_url: string | null }>> {
  const { data } = await api.get('/auth/search', { params: { q: query } });
  return data;
}

// ── Groups ─────────────────────────────────────────────────────────────────────

export async function createGroup(data: { name: string; description?: string; privacy?: string }) {
  const { data: result } = await api.post('/groups', data);
  return result;
}

export async function searchGroups(query: string) {
  const { data } = await api.get('/groups/search', { params: { q: query } });
  return data;
}

export async function fetchMyGroups() {
  const { data } = await api.get('/groups/my');
  return data;
}

export async function fetchGroup(slug: string) {
  const { data } = await api.get(`/groups/${encodeURIComponent(slug)}`);
  return data;
}

export async function updateGroup(slug: string, data: { name?: string; description?: string; privacy?: string }) {
  const { data: result } = await api.put(`/groups/${encodeURIComponent(slug)}`, data);
  return result;
}

export async function deleteGroup(slug: string) {
  await api.delete(`/groups/${encodeURIComponent(slug)}`);
}

export async function joinGroup(slug: string) {
  const { data } = await api.post(`/groups/${encodeURIComponent(slug)}/join`);
  return data;
}

export async function leaveGroup(slug: string) {
  await api.post(`/groups/${encodeURIComponent(slug)}/leave`);
}

export async function fetchGroupMembers(slug: string) {
  const { data } = await api.get(`/groups/${encodeURIComponent(slug)}/members`);
  return data;
}

export async function fetchGroupRequests(slug: string) {
  const { data } = await api.get(`/groups/${encodeURIComponent(slug)}/requests`);
  return data;
}

export async function approveGroupRequest(slug: string, username: string) {
  const { data } = await api.post(`/groups/${encodeURIComponent(slug)}/members/${encodeURIComponent(username)}/approve`);
  return data;
}

export async function denyGroupRequest(slug: string, username: string) {
  await api.post(`/groups/${encodeURIComponent(slug)}/members/${encodeURIComponent(username)}/deny`);
}

export async function kickGroupMember(slug: string, username: string) {
  await api.post(`/groups/${encodeURIComponent(slug)}/members/${encodeURIComponent(username)}/kick`);
}

export async function changeGroupMemberRole(slug: string, username: string, role: string) {
  const { data } = await api.put(`/groups/${encodeURIComponent(slug)}/members/${encodeURIComponent(username)}/role`, { role });
  return data;
}

export async function inviteToGroup(slug: string, username: string) {
  const { data } = await api.post(`/groups/${encodeURIComponent(slug)}/invite`, { username });
  return data;
}

export default api;
