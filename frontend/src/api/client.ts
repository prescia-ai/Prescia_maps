import axios from 'axios';
import type {
  LocationFeatureCollection,
  LinearFeatureCollection,
  HeatmapPoint,
  ScoreResponse,
  LandAccessResponse,
  LandAccessOverrideCreate,
  LandAccessOverrideResponse,
  ImportSummaryResponse,
} from '../types';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15_000,
});

export async function fetchLocations(): Promise<LocationFeatureCollection> {
  const { data } = await api.get<LocationFeatureCollection>('/locations');
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
