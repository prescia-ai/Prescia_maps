import { useQuery } from '@tanstack/react-query';
import { fetchFeatures } from '../api/client';

export function useFeatures() {
  return useQuery({
    queryKey: ['features'],
    queryFn: fetchFeatures,
  });
}
