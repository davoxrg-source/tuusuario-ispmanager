import { apiClient } from "./client";
import type { Installation, InstallationInput, RouteDistance } from "./types";

export async function listInstallations(): Promise<Installation[]> {
  const { data } = await apiClient.get<Installation[]>("/installations");
  return data;
}

export async function getInstallation(id: string): Promise<Installation> {
  const { data } = await apiClient.get<Installation>(`/installations/${id}`);
  return data;
}

export async function createInstallation(payload: InstallationInput): Promise<Installation> {
  const { data } = await apiClient.post<Installation>("/installations", payload);
  return data;
}

export async function updateInstallation(
  id: string,
  payload: Partial<InstallationInput>,
): Promise<Installation> {
  const { data } = await apiClient.patch<Installation>(`/installations/${id}`, payload);
  return data;
}

export async function deleteInstallation(id: string): Promise<void> {
  await apiClient.delete(`/installations/${id}`);
}

export async function calculateRouteDistance(installationIds: string[]): Promise<RouteDistance> {
  const { data } = await apiClient.post<RouteDistance>("/installations/route-distance", {
    installation_ids: installationIds,
  });
  return data;
}
