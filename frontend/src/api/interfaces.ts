import { apiClient } from "./client";
import type {
  Bridge,
  BridgePort,
  IpAddress,
  IpAddressInput,
  PppoeServerSetupInput,
  RouterInterface,
} from "./types";

export async function listInterfaces(deviceId: string): Promise<RouterInterface[]> {
  const { data } = await apiClient.get<RouterInterface[]>(`/devices/${deviceId}/interfaces`);
  return data;
}

export async function listIpAddresses(deviceId: string): Promise<IpAddress[]> {
  const { data } = await apiClient.get<IpAddress[]>(`/devices/${deviceId}/ip-addresses`);
  return data;
}

export async function addIpAddress(deviceId: string, payload: IpAddressInput): Promise<void> {
  await apiClient.post(`/devices/${deviceId}/ip-addresses`, payload);
}

export async function removeIpAddress(deviceId: string, ipId: string): Promise<void> {
  await apiClient.delete(`/devices/${deviceId}/ip-addresses/${ipId}`);
}

export async function listBridges(deviceId: string): Promise<Bridge[]> {
  const { data } = await apiClient.get<Bridge[]>(`/devices/${deviceId}/bridges`);
  return data;
}

export async function createBridge(deviceId: string, name: string): Promise<void> {
  await apiClient.post(`/devices/${deviceId}/bridges`, { name });
}

export async function removeBridge(deviceId: string, bridgeId: string): Promise<void> {
  await apiClient.delete(`/devices/${deviceId}/bridges/${bridgeId}`);
}

export async function listBridgePorts(deviceId: string): Promise<BridgePort[]> {
  const { data } = await apiClient.get<BridgePort[]>(`/devices/${deviceId}/bridge-ports`);
  return data;
}

export async function addBridgePort(
  deviceId: string,
  bridgeName: string,
  iface: string,
): Promise<void> {
  await apiClient.post(`/devices/${deviceId}/bridges/${bridgeName}/ports`, { interface: iface });
}

export async function removeBridgePort(deviceId: string, portId: string): Promise<void> {
  await apiClient.delete(`/devices/${deviceId}/bridge-ports/${portId}`);
}

export async function setupPppoeServer(
  deviceId: string,
  payload: PppoeServerSetupInput,
): Promise<void> {
  await apiClient.post(`/devices/${deviceId}/pppoe-server`, payload);
}
