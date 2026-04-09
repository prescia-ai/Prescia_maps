import { useQuery } from '@tanstack/react-query';
import { fetchMyPins } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import type { UserPin } from '../types';

export function useMyPins() {
  const { user } = useAuth();
  return useQuery<{ pins: UserPin[]; total: number }>({
    queryKey: ['my-pins'],
    queryFn: () => fetchMyPins(),
    enabled: !!user,
  });
}
