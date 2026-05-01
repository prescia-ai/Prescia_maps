import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createPlan,
  deletePlan,
  duplicatePlan,
  fetchMyPlans,
  fetchPlan,
  fetchPlanMapPins,
  updatePlan,
  updatePlanStatus,
} from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import type { HuntPlan, HuntPlanMapPin } from '../types';

// ── Query key constants ────────────────────────────────────────────────────────

export const HUNT_PLANS_KEYS = {
  all: ['hunt-plans'] as const,
  lists: () => [...HUNT_PLANS_KEYS.all, 'list'] as const,
  list: (params?: object) => [...HUNT_PLANS_KEYS.lists(), params] as const,
  detail: (id: string) => [...HUNT_PLANS_KEYS.all, 'detail', id] as const,
  mapPins: (includeArchived = false) =>
    [...HUNT_PLANS_KEYS.all, 'map-pins', includeArchived] as const,
};

// ── Query hooks ────────────────────────────────────────────────────────────────

export function useMyPlans(params?: {
  q?: string;
  sort?: string;
  order?: string;
  site_type?: string;
  status?: string;
  include_archived?: boolean;
}) {
  const { user } = useAuth();
  return useQuery<{ plans: HuntPlan[]; total: number }>({
    queryKey: HUNT_PLANS_KEYS.list(params),
    queryFn: () => fetchMyPlans(params),
    enabled: !!user,
  });
}

export function usePlan(planId: string | undefined) {
  const { user } = useAuth();
  return useQuery<HuntPlan>({
    queryKey: HUNT_PLANS_KEYS.detail(planId ?? ''),
    queryFn: () => fetchPlan(planId!),
    enabled: !!user && !!planId,
  });
}

export function usePlanMapPins(includeArchived = false) {
  const { user } = useAuth();
  return useQuery<HuntPlanMapPin[]>({
    queryKey: HUNT_PLANS_KEYS.mapPins(includeArchived),
    queryFn: () => fetchPlanMapPins(includeArchived),
    enabled: !!user,
    staleTime: 60_000,
  });
}

// ── Mutation hooks ─────────────────────────────────────────────────────────────

export function useCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createPlan,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.lists() });
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.mapPins() });
    },
  });
}

export function useUpdatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, payload }: { planId: string; payload: Parameters<typeof updatePlan>[1] }) =>
      updatePlan(planId, payload),
    onSuccess: (updated) => {
      qc.setQueryData(HUNT_PLANS_KEYS.detail(updated.id), updated);
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.lists() });
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.mapPins() });
    },
  });
}

export function useDeletePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deletePlan,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.lists() });
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.mapPins() });
    },
  });
}

export function useUpdatePlanStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, status }: { planId: string; status: string }) =>
      updatePlanStatus(planId, status),
    onSuccess: (updated) => {
      qc.setQueryData(HUNT_PLANS_KEYS.detail(updated.id), updated);
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.lists() });
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.mapPins() });
    },
  });
}

export function useDuplicatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: duplicatePlan,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.lists() });
      qc.invalidateQueries({ queryKey: HUNT_PLANS_KEYS.mapPins() });
    },
  });
}
