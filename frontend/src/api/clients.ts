import { apiClient } from "./client";
import type { Client, ClientInput } from "./types";

export async function listClients(): Promise<Client[]> {
  const { data } = await apiClient.get<Client[]>("/clients");
  return data;
}

export async function createClient(payload: ClientInput): Promise<Client> {
  const { data } = await apiClient.post<Client>("/clients", payload);
  return data;
}

export async function updateClient(id: string, payload: Partial<ClientInput>): Promise<Client> {
  const { data } = await apiClient.patch<Client>(`/clients/${id}`, payload);
  return data;
}

export async function deleteClient(id: string): Promise<void> {
  await apiClient.delete(`/clients/${id}`);
}

export async function suspendClient(id: string): Promise<Client> {
  const { data } = await apiClient.post<Client>(`/clients/${id}/suspend`);
  return data;
}

export async function reactivateClient(id: string): Promise<Client> {
  const { data } = await apiClient.post<Client>(`/clients/${id}/reactivate`);
  return data;
}
