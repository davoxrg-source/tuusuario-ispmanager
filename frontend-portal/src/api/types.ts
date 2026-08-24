export type ClientStatus = "active" | "suspended" | "cancelled";

export interface ClientProfile {
  id: string;
  full_name: string;
  identification: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  plan_id: string | null;
  status: ClientStatus;
  is_online: boolean;
  last_seen_at: string | null;
  pending_credit: number;
  pending_reconnection_fee: boolean;
}

export interface ProfileUpdateInput {
  phone?: string | null;
  email?: string | null;
  address?: string | null;
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
  promise_to_pay_until: string | null;
  late_fee_amount: number;
  late_fee_applied_at: string | null;
  folio: string | null;
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

export interface PaymentReportInput {
  invoice_id: string;
  amount: number;
  method: string;
  reference?: string | null;
  note?: string | null;
}

export type TicketStatus = "open" | "in_progress" | "waiting_client" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "urgent";
export type TicketCategory = "billing" | "technical" | "installation" | "other";

export interface Ticket {
  id: string;
  client_id: string | null;
  created_by_user_id: string | null;
  created_by_client_id: string | null;
  assigned_to_user_id: string | null;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  category: TicketCategory;
  created_at: string;
  updated_at: string;
}

export interface TicketInput {
  subject: string;
  description: string;
  priority?: TicketPriority;
  category?: TicketCategory;
}

export interface TicketReply {
  id: string;
  ticket_id: string;
  author_user_id: string | null;
  author_client_id: string | null;
  body: string;
  created_at: string;
}
