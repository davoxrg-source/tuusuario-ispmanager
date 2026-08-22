import { apiClient } from "./client";
import type { WanBalancingInput, WanBalancingResponse } from "./types";

export async function listRoutes(deviceId: string): Promise<Record<string, unknown>[]> {
  const { data } = await apiClient.get(`/devices/${deviceId}/routes`);
  return data;
}

export async function listMangleRules(deviceId: string): Promise<Record<string, unknown>[]> {
  const { data } = await apiClient.get(`/devices/${deviceId}/mangle-rules`);
  return data;
}

export async function listNatRules(deviceId: string): Promise<Record<string, unknown>[]> {
  const { data } = await apiClient.get(`/devices/${deviceId}/nat-rules`);
  return data;
}

export async function previewWanBalancing(
  deviceId: string,
  payload: WanBalancingInput,
): Promise<WanBalancingResponse> {
  const { data } = await apiClient.post<WanBalancingResponse>(
    `/devices/${deviceId}/wan-balancing/preview`,
    payload,
  );
  return data;
}

export async function applyWanBalancing(
  deviceId: string,
  payload: WanBalancingInput,
): Promise<WanBalancingResponse> {
  const { data } = await apiClient.post<WanBalancingResponse>(
    `/devices/${deviceId}/wan-balancing/apply`,
    payload,
  );
  return data;
}
