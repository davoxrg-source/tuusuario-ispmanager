import { apiClient, TOKEN_STORAGE_KEY } from "./client";
import type { UserRead } from "./types";

export async function login(email: string, password: string): Promise<void> {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  const { data } = await apiClient.post<{ access_token: string }>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
}

export function logout(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export async function fetchCurrentUser(): Promise<UserRead> {
  const { data } = await apiClient.get<UserRead>("/auth/me");
  return data;
}

export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem(TOKEN_STORAGE_KEY));
}
