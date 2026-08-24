import { apiClient, TOKEN_STORAGE_KEY } from "./client";
import type { ClientProfile } from "./types";

export async function login(identification: string, password: string): Promise<void> {
  const form = new URLSearchParams();
  // "username" es el nombre fijo del campo de OAuth2PasswordRequestForm en
  // el backend -- acá lleva la identificación, no un correo.
  form.set("username", identification);
  form.set("password", password);
  const { data } = await apiClient.post<{ access_token: string }>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
}

export function logout(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export async function fetchMyProfile(): Promise<ClientProfile> {
  const { data } = await apiClient.get<ClientProfile>("/auth/me");
  return data;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiClient.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem(TOKEN_STORAGE_KEY));
}
