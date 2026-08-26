import axios from "axios";
import * as SecureStore from "expo-secure-store";

// IP del servidor de desarrollo (mismo backend real que usan frontend/ y
// frontend-portal/) -- en producción esto se arma vía una variable de
// entorno de build de Expo (EXPO_PUBLIC_API_BASE_URL), no hardcodeado.
const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://10.100.8.10:8000/api/portal";

export const TOKEN_STORAGE_KEY = "ispmanager_client_token";

export const apiClient = axios.create({ baseURL: API_BASE_URL });

apiClient.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_STORAGE_KEY, token);
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_STORAGE_KEY);
}

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_STORAGE_KEY);
}
