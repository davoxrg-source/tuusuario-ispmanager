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
  mac_address: string | null;
  api_port: number;
  api_use_tls: boolean;
  ssh_port: number;
  username: string;
  model: string | null;
  routeros_version: string | null;
  status: DeviceStatus;
  last_seen_at: string | null;
}

export interface DiscoveredDevice {
  mac_address: string;
  ip_address: string;
  identity: string | null;
  version: string | null;
  platform: string | null;
  seen_seconds_ago: number;
}

export interface MikrotikDeviceInput {
  name: string;
  site?: string | null;
  host: string;
  mac_address?: string | null;
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
  resolved_via_mac: boolean;
  updated_host: string | null;
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

export interface RouterInterface {
  id: string;
  name: string;
  type: string;
  running: boolean;
  disabled: boolean;
  mac_address: string | null;
  mtu: number | null;
}

export interface IpAddress {
  id: string;
  address: string;
  network: string | null;
  interface: string;
  disabled: boolean;
}

export interface IpAddressInput {
  interface: string;
  address: string;
}

export interface Bridge {
  id: string;
  name: string;
  disabled: boolean;
}

export interface BridgePort {
  id: string;
  interface: string;
  bridge: string;
}

export interface PppoeServerSetupInput {
  interface: string;
  service_name: string;
  pool_start: string;
  pool_end: string;
  profile_name: string;
  local_address: string;
}

export type WanConnectionType = "static" | "dhcp" | "pppoe";

export interface WanLinkInput {
  interface: string;
  connection_type: WanConnectionType;
  distance: number;
  // Solo para connection_type === "static"
  gateway?: string;
  address?: string;
  // Solo para connection_type === "pppoe"
  pppoe_username?: string;
  pppoe_password?: string;
  pppoe_service_name?: string;
}

export interface PublicBlockPin {
  cidr: string;
  wan_interface: string;
}

export interface WanBalancingInput {
  lan_interface: string;
  wans: WanLinkInput[];
  public_blocks: PublicBlockPin[];
}

export interface WanCommandResult {
  description: string;
  path: string;
  params: Record<string, string>;
  executed: boolean;
  error: string | null;
}

export interface WanBalancingResponse {
  commands: WanCommandResult[];
  applied: boolean;
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
  // % del plan garantizado como piso aunque el enlace esté saturado (ver
  // services/mikrotik/qos.py en el backend). Puede hacer ráfaga hasta 100%.
  guaranteed_floor_percent: number;
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
  ip_address?: string | null;
}

export type InvoiceStatus = "pending" | "paid" | "overdue" | "cancelled";

// QoS: infraestructura de shaping de UN plan en UN equipo (address-list +
// PCQ + mangle + queue tree). Se aplica una sola vez por plan por equipo —
// no por cliente. Ver services/mikrotik/qos.py en el backend.
export interface QosPlanBootstrapInput {
  lan_interface: string;
  wan_interface: string;
  priority_tcp_ports: number[];
  priority_udp_ports: number[];
  realtime_tcp_max_size: number;
  realtime_udp_max_size: number;
}

export interface QosPlanBootstrapResponse {
  commands: WanCommandResult[];
  applied: boolean;
}

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
