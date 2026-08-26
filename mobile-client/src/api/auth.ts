import { apiClient, clearToken, setToken } from "./client";
import type { ClientProfile } from "./types";

export async function login(identification: string, password: string): Promise<void> {
  const form = new URLSearchParams();
  // "username" es el nombre fijo del campo de OAuth2PasswordRequestForm en
  // el backend -- acá lleva la identificación, no un correo (mismo
  // criterio que frontend-portal/src/api/auth.ts).
  form.set("username", identification);
  form.set("password", password);
  const { data } = await apiClient.post<{ access_token: string }>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  await setToken(data.access_token);
}

export async function logout(): Promise<void> {
  await clearToken();
}

export async function fetchMyProfile(): Promise<ClientProfile> {
  const { data } = await apiClient.get<ClientProfile>("/auth/me");
  return data;
}
