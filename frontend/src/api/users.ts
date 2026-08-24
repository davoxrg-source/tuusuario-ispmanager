import { apiClient } from "./client";
import type { StaffName, UserInput, UserRead } from "./types";

export async function listUsers(): Promise<UserRead[]> {
  const { data } = await apiClient.get<UserRead[]>("/users");
  return data;
}

// Abierto a cualquier usuario autenticado (a diferencia de listUsers, que es
// admin-only) -- solo id + nombre, para selects como "a qué técnico se le
// asigna esto" en Almacén.
export async function listStaffDirectory(): Promise<StaffName[]> {
  const { data } = await apiClient.get<StaffName[]>("/users/directory");
  return data;
}

export async function createUser(payload: UserInput): Promise<UserRead> {
  const { data } = await apiClient.post<UserRead>("/users", payload);
  return data;
}

export async function updateUser(id: string, payload: Partial<UserInput>): Promise<UserRead> {
  const { data } = await apiClient.patch<UserRead>(`/users/${id}`, payload);
  return data;
}
