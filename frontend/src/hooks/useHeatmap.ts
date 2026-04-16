import { useQuery } from '@tanstack/react-query';
import { fetchHeatmap } from '../api/client';

/**
 * Bucket a raw zoom level into one of three zones so we only refetch
 * when the view meaningfully changes (not on every single zoom tick).
 *   low  → ≤7  (state / national level)
 *   mid  → 8–12 (county level)
 *   high → ≥13  (street level)
 */
export function zoomBucket(zoom: number): 'low' | 'mid' | 'high' {
  if (zoom <= 7) return 'low';
  if (zoom <= 12) return 'mid';
  return 'high';
}

export function useHeatmap(zoom: number = 10) {
  const bucket = zoomBucket(zoom);
  return useQuery({
    queryKey: ['heatmap', bucket],
    queryFn: () => fetchHeatmap(zoom),
    staleTime: 5 * 60 * 1000, // 5-minute cache per zoom bucket
  });
}
