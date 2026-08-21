import { apiClient } from "./client";
import type {
  ActivePppSession,
  ConnectionTestResult,
  DeviceMetric,
  DeviceResourceStatus,
  DiscoveredDevice,
  MikrotikDevice,
  MikrotikDeviceInput,
} from "./types";

export async function listDevices(): Promise<MikrotikDevice[]> {
  const { data } = await apiClient.get<MikrotikDevice[]>("/devices");
  return data;
}

export async function listDiscoveredDevices(): Promise<DiscoveredDevice[]> {
  const { data } = await apiClient.get<DiscoveredDevice[]>("/devices/discovered");
  return data;
}

export async function getDevice(id: string): Promise<MikrotikDevice> {
  const { data } = await apiClient.get<MikrotikDevice>(`/devices/${id}`);
  return data;
}

export async function createDevice(payload: MikrotikDeviceInput): Promise<MikrotikDevice> {
  const { data } = await apiClient.post<MikrotikDevice>("/devices", payload);
  return data;
}

export async function updateDevice(
  id: string,
  payload: Partial<MikrotikDeviceInput>,
): Promise<MikrotikDevice> {
  const { data } = await apiClient.patch<MikrotikDevice>(`/devices/${id}`, payload);
  return data;
}

export async function deleteDevice(id: string): Promise<void> {
  await apiClient.delete(`/devices/${id}`);
}

export async function testConnection(id: string): Promise<ConnectionTestResult> {
  const { data } = await apiClient.post<ConnectionTestResult>(`/devices/${id}/test-connection`);
  return data;
}

export async function getDeviceStatus(id: string): Promise<DeviceResourceStatus> {
  const { data } = await apiClient.get<DeviceResourceStatus>(`/devices/${id}/status`);
  return data;
}

export async function rebootDevice(id: string): Promise<void> {
  await apiClient.post(`/devices/${id}/reboot`);
}

export async function getDeviceMetrics(id: string, limit = 100): Promise<DeviceMetric[]> {
  const { data } = await apiClient.get<DeviceMetric[]>(`/devices/${id}/metrics`, { params: { limit } });
  return data;
}

export async function getActiveSessions(id: string): Promise<ActivePppSession[]> {
  const { data } = await apiClient.get<ActivePppSession[]>(`/devices/${id}/active-sessions`);
  return data;
}
