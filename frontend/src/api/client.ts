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

export default api;
