import { apiClient } from "./client";
import type { Client, QosPlanBootstrapInput, QosPlanBootstrapResponse } from "./types";

export async function previewQosPlanBootstrap(
  deviceId: string,
  planId: string,
  payload: QosPlanBootstrapInput,
): Promise<QosPlanBootstrapResponse> {
  const { data } = await apiClient.post<QosPlanBootstrapResponse>(
    `/devices/${deviceId}/qos-plans/${planId}/preview`,
    payload,
  );
  return data;
}

export async function applyQosPlanBootstrap(
  deviceId: string,
  planId: string,
  payload: QosPlanBootstrapInput,
): Promise<QosPlanBootstrapResponse> {
  const { data } = await apiClient.post<QosPlanBootstrapResponse>(
    `/devices/${deviceId}/qos-plans/${planId}/apply`,
    payload,
  );
  return data;
}

export async function removeQosPlanBootstrap(deviceId: string, planId: string): Promise<void> {
  await apiClient.delete(`/devices/${deviceId}/qos-plans/${planId}`);
}

export async function provisionClientQos(clientId: string): Promise<Client> {
  const { data } = await apiClient.post<Client>(`/clients/${clientId}/qos/provision`);
  return data;
}

export async function removeClientQos(clientId: string): Promise<void> {
  await apiClient.delete(`/clients/${clientId}/qos`);
}
