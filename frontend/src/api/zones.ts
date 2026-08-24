import { apiClient } from "./client";
import type { Zone, ZoneInput } from "./types";

export async function listZones(): Promise<Zone[]> {
  const { data } = await apiClient.get<Zone[]>("/zones");
  return data;
}

export async function createZone(payload: ZoneInput): Promise<Zone> {
  const { data } = await apiClient.post<Zone>("/zones", payload);
  return data;
}

export async function updateZone(id: string, payload: Partial<ZoneInput>): Promise<Zone> {
  const { data } = await apiClient.patch<Zone>(`/zones/${id}`, payload);
  return data;
}

export async function deleteZone(id: string): Promise<void> {
  await apiClient.delete(`/zones/${id}`);
}
