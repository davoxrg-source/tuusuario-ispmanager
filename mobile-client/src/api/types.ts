// Mismos tipos que frontend-portal/src/api/types.ts -- misma API
// (/api/portal/*), copiados en vez de compartidos (ver decisión de
// diseño de Fase 6: 2 proyectos separados, sin tooling de monorepo).

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

export interface PaymentReportInput {
  invoice_id: string;
  amount: number;
  method: string;
  reference?: string | null;
  note?: string | null;
}

export interface CheckoutUrlRead {
  checkout_url: string;
  reference: string;
}
