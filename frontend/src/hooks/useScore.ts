import { useQuery } from '@tanstack/react-query';
import { fetchScore } from '../api/client';

export function useScore(lat: number | null, lon: number | null) {
  return useQuery({
    queryKey: ['score', lat, lon],
    queryFn: () => fetchScore(lat!, lon!),
    enabled: lat !== null && lon !== null,
  });
}
