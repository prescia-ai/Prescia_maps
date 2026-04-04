import { useQuery } from '@tanstack/react-query';
import { fetchLocations } from '../api/client';

export function useLocations() {
  return useQuery({
    queryKey: ['locations'],
    queryFn: fetchLocations,
  });
}
