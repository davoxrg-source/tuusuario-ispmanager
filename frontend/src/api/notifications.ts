import { apiClient } from "./client";
import type { Notification, NotificationChannel, NotificationStatus } from "./types";

export interface NotificationFilters {
  client_id?: string;
  status_filter?: NotificationStatus;
  channel?: NotificationChannel;
}

export async function listNotifications(filters: NotificationFilters = {}): Promise<Notification[]> {
  const { data } = await apiClient.get<Notification[]>("/notifications", { params: filters });
  return data;
}
