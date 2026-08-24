import axios from "axios";

// Clave de localStorage distinta a la del panel de staff (ispmanager_token)
// -- por si alguien usa el mismo navegador para ambas cosas, no se pisan.
export const TOKEN_STORAGE_KEY = "ispmanager_portal_token";

export const apiClient = axios.create({
  baseURL: "/api/portal",
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      if (window.location.pathname !== "/portal/login") {
        window.location.href = "/portal/login";
      }
    }
    return Promise.reject(error);
  },
);
