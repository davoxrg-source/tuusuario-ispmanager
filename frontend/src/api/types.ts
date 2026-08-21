export type UserRole = "admin" | "technician";

export interface UserRead {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export type DeviceStatus = "online" | "offline" | "unknown";

export interface MikrotikDevice {
  id: string;
  name: string;
  site: string | null;
  host: string;
  api_port: number;
  api_use_tls: boolean;
  ssh_port: number;
  username: string;
  model: string | null;
  routeros_version: string | null;
  status: DeviceStatus;
  last_seen_at: string | null;
}

export interface MikrotikDeviceInput {
  name: string;
  site?: string | null;
  host: string;
  api_port: number;
  api_use_tls: boolean;
  ssh_port: number;
  username: string;
  password: string;
}

export interface ConnectionTestResult {
  success: boolean;
  method: string;
  message: string;
  identity: string | null;
  routeros_version: string | null;
  uptime_seconds: number | null;
}

export interface DeviceResourceStatus {
  cpu_load_percent: number | null;
  memory_used_bytes: number | null;
  memory_total_bytes: number | null;
  uptime_seconds: number | null;
  active_ppp_sessions: number | null;
}

export interface ActivePppSession {
  name: string;
  address: string | null;
  uptime: string | null;
  caller_id: string | null;
}

export interface DeviceMetric {
  id: string;
  device_id: string;
  recorded_at: string;
  cpu_load_percent: number | null;
  memory_used_bytes: number | null;
  memory_total_bytes: number | null;
  uptime_seconds: number | null;
  active_ppp_sessions: number | null;
  interfaces: { list: { name: string; rx_bytes: number; tx_bytes: number; running: boolean }[] } | null;
}

export interface Plan {
  id: string;
  name: string;
  download_speed_mbps: number;
  upload_speed_mbps: number;
  price: number;
  currency: string;
}

export type ClientStatus = "active" | "suspended" | "cancelled";

export interface Client {
  id: string;
  full_name: string;
  identification: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  plan_id: string | null;
  mikrotik_device_id: string | null;
  pppoe_username: string | null;
  ip_address: string | null;
  status: ClientStatus;
}

export interface ClientInput {
  full_name: string;
  identification?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  plan_id?: string | null;
  mikrotik_device_id?: string | null;
  pppoe_username?: string | null;
  pppoe_password?: string | null;
  ip_address?: string | null;
}

export type InvoiceStatus = "pending" | "paid" | "overdue" | "cancelled";

export interface Invoice {
  id: string;
  client_id: string;
  period_start: string;
  period_end: string;
  due_date: string;
  amount: number;
  status: InvoiceStatus;
  paid_at: string | null;
}
