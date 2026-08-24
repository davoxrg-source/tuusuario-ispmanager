import { apiClient } from "./client";
import type { HotspotProfile, HotspotProfileInput, HotspotVoucher, HotspotVoucherStatus } from "./types";

export async function listHotspotProfiles(): Promise<HotspotProfile[]> {
  const { data } = await apiClient.get<HotspotProfile[]>("/hotspot-profiles");
  return data;
}

export async function createHotspotProfile(payload: HotspotProfileInput): Promise<HotspotProfile> {
  const { data } = await apiClient.post<HotspotProfile>("/hotspot-profiles", payload);
  return data;
}

export async function updateHotspotProfile(
  id: string,
  payload: Partial<HotspotProfileInput>,
): Promise<HotspotProfile> {
  const { data } = await apiClient.patch<HotspotProfile>(`/hotspot-profiles/${id}`, payload);
  return data;
}

export async function deleteHotspotProfile(id: string): Promise<void> {
  await apiClient.delete(`/hotspot-profiles/${id}`);
}

export async function listHotspotVouchers(filters?: {
  profile_id?: string;
  status_filter?: HotspotVoucherStatus;
  batch_id?: string;
}): Promise<HotspotVoucher[]> {
  const { data } = await apiClient.get<HotspotVoucher[]>("/hotspot-vouchers", { params: filters });
  return data;
}

export async function generateVoucherBatch(
  profile_id: string,
  quantity: number,
): Promise<HotspotVoucher[]> {
  const { data } = await apiClient.post<HotspotVoucher[]>("/hotspot-vouchers/batch", {
    profile_id,
    quantity,
  });
  return data;
}

export async function sellVoucher(id: string): Promise<HotspotVoucher> {
  const { data } = await apiClient.post<HotspotVoucher>(`/hotspot-vouchers/${id}/sell`);
  return data;
}

export async function voidVoucher(id: string): Promise<HotspotVoucher> {
  const { data } = await apiClient.post<HotspotVoucher>(`/hotspot-vouchers/${id}/void`);
  return data;
}
