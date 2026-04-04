import { useQuery } from '@tanstack/react-query';
import { fetchHeatmap } from '../api/client';

export function useHeatmap() {
  return useQuery({
    queryKey: ['heatmap'],
    queryFn: fetchHeatmap,
  });
}
