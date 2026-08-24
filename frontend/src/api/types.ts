export type UserRole = "admin" | "technician" | "finance";

export interface Zone {
  id: string;
  name: string;
  description: string | null;
}

export interface ZoneInput {
  name: string;
  description?: string | null;
}

export interface UserRead {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  zones: Zone[];
}

export interface StaffName {
  id: string;
  full_name: string;
}

export interface UserInput {
  full_name: string;
  email: string;
  password?: string;
  role: UserRole;
  is_active?: boolean;
  zone_ids: string[];
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
  zone_id: string | null;
  latitude: number | null;
  longitude: number | null;
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
  zone_id?: string | null;
  latitude?: number | null;
  longitude?: number | null;
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

export interface PollAttempt {
  id: string;
  device_id: string | null;
  job_type: string;
  attempt_number: number;
  max_attempts: number;
  status: "success" | "failure";
  error_message: string | null;
  duration_ms: number | null;
  attempted_at: string;
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
  // IP pública entregada por proxy-ARP (ver DeviceService.provision_client_public_ip
  // en el backend) -- distinta de ip_address, que es la IP privada de LAN
  // usada para QoS/suspensión. Los 3 campos van juntos.
  public_ip_address: string | null;
  public_ip_provider_interface: string | null;
  public_ip_lan_interface: string | null;
  status: ClientStatus;
  // Conectividad real (tabla ARP del Mikrotik, actualizada por el poller
  // cada DEVICE_POLL_INTERVAL_SECONDS) -- distinto de `status`, que es el
  // estado administrativo/de facturación del contrato.
  is_online: boolean;
  last_seen_at: string | null;
  zone_id: string | null;
  latitude: number | null;
  longitude: number | null;
  portal_active: boolean;
}

export interface PortalActivateResult {
  password: string;
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
  public_ip_address?: string | null;
  public_ip_provider_interface?: string | null;
  public_ip_lan_interface?: string | null;
  zone_id?: string | null;
  latitude?: number | null;
  longitude?: number | null;
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
  promise_to_pay_until: string | null;
  late_fee_amount: number;
  late_fee_applied_at: string | null;
  folio: string | null;
}

export interface BulkActionResultItem {
  id: string;
  ok: boolean;
  detail: string | null;
}

export interface BulkActionResult {
  results: BulkActionResultItem[];
}

export interface PaymentAccount {
  id: string;
  name: string;
  kind: string;
  is_active: boolean;
}

export interface AccountBalance {
  id: string;
  name: string;
  kind: string;
  total: number;
}

export interface BillingSettings {
  generate_invoice_days_before_due: number;
  suspend_days_after_due: number;
  proration_enabled: boolean;
  proration_min_days: number;
  proration_target: "current_invoice" | "next_invoice";
  late_fee_enabled: boolean;
  late_fee_amount: number;
  late_fee_apply_hour: number;
  reconnection_fee_mode: "off" | "on_suspend" | "on_next_invoice";
  reconnection_fee_amount: number;
  invoice_folio_prefix: string;
  invoice_folio_next_number: number;
  payment_reminder_enabled: boolean;
  payment_reminder_days_before_due: number;
}

export interface Supplier {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  notes: string | null;
}

export interface SupplierInput {
  name: string;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
}

export interface InventoryItem {
  id: string;
  name: string;
  category: string;
  quantity: number;
  unit_cost: number | null;
  supplier_id: string | null;
  notes: string | null;
}

export interface InventoryItemInput {
  name: string;
  category?: string;
  unit_cost?: number | null;
  supplier_id?: string | null;
  notes?: string | null;
}

export type MovementReason = "purchase" | "assignment" | "installation" | "return" | "adjustment" | "loss";

export interface InventoryMovement {
  id: string;
  item_id: string;
  reason: MovementReason;
  quantity_delta: number;
  assigned_to_user_id: string | null;
  client_id: string | null;
  note: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface InventoryMovementInput {
  item_id: string;
  reason: MovementReason;
  quantity_delta: number;
  assigned_to_user_id?: string | null;
  client_id?: string | null;
  note?: string | null;
}

export interface TechnicianBalance {
  user_id: string;
  user_name: string;
  item_id: string;
  item_name: string;
  balance: number;
}

export type InstallationStatus = "scheduled" | "completed" | "cancelled";

export interface Installation {
  id: string;
  client_id: string;
  assigned_technician_id: string | null;
  scheduled_date: string;
  status: InstallationStatus;
  notes: string | null;
  created_at: string;
}

export interface InstallationInput {
  client_id: string;
  assigned_technician_id?: string | null;
  scheduled_date: string;
  status?: InstallationStatus;
  notes?: string | null;
}

export interface RouteLeg {
  from_id: string;
  to_id: string;
  km: number;
}

export interface RouteDistance {
  total_km: number;
  legs: RouteLeg[];
}

export interface ContractTemplate {
  id: string;
  name: string;
  body: string;
}

export interface ContractTemplateInput {
  name: string;
  body: string;
}

export type ContractStatus = "draft" | "signed" | "void";

export interface Contract {
  id: string;
  client_id: string | null;
  template_id: string | null;
  rendered_body: string;
  status: ContractStatus;
  signer_name: string | null;
  signer_identification: string | null;
  signature_image: string | null;
  signed_at: string | null;
  signer_ip: string | null;
  witnessed_by_user_id: string | null;
  created_by_user_id: string;
  created_at: string;
}

export interface ContractCreateInput {
  client_id: string;
  template_id: string;
}

export interface ContractSignInput {
  signer_name: string;
  signer_identification?: string | null;
  signature_image: string;
}

export type PaymentReportStatus = "pending" | "confirmed" | "rejected";

export interface PaymentReport {
  id: string;
  invoice_id: string;
  client_id: string;
  amount: number;
  method: string;
  reference: string | null;
  note: string | null;
  status: PaymentReportStatus;
  reported_at: string;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
}

export type NotificationChannel = "email" | "push";
export type NotificationStatus = "sent" | "failed";

export interface Notification {
  id: string;
  client_id: string;
  channel: NotificationChannel;
  event_type: string;
  recipient: string;
  subject: string;
  status: NotificationStatus;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}

export type WompiTransactionStatus = "pending" | "approved" | "declined" | "voided" | "error";

export interface WompiTransaction {
  id: string;
  invoice_id: string;
  reference: string;
  wompi_transaction_id: string | null;
  amount_in_cents: number;
  status: WompiTransactionStatus;
  created_at: string;
  updated_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

export interface ApiKeyCreateResult extends ApiKey {
  key: string;
}
