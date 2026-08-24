import { apiClient } from "./client";
import type { ApiKey, ApiKeyCreateResult } from "./types";

export async function listApiKeys(): Promise<ApiKey[]> {
  const { data } = await apiClient.get<ApiKey[]>("/api-keys");
  return data;
}

export async function createApiKey(name: string): Promise<ApiKeyCreateResult> {
  const { data } = await apiClient.post<ApiKeyCreateResult>("/api-keys", { name });
  return data;
}

export async function revokeApiKey(id: string): Promise<ApiKey> {
  const { data } = await apiClient.post<ApiKey>(`/api-keys/${id}/revoke`);
  return data;
}
