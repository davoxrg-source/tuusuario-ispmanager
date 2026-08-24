import { apiClient } from "./client";
import type {
  AccountBalance,
  BillingSettings,
  BulkActionResult,
  Invoice,
  PaymentAccount,
  PaymentReport,
  PaymentReportStatus,
} from "./types";

export async function listInvoices(): Promise<Invoice[]> {
  const { data } = await apiClient.get<Invoice[]>("/invoices");
  return data;
}

export async function listClientInvoices(clientId: string): Promise<Invoice[]> {
  const { data } = await apiClient.get<Invoice[]>(`/clients/${clientId}/invoices`);
  return data;
}

export interface PaymentInput {
  amount: number;
  method: string;
  reference?: string | null;
  payment_account_id?: string | null;
}

export async function payInvoice(invoiceId: string, payload: PaymentInput): Promise<Invoice> {
  const { data } = await apiClient.post<Invoice>(`/invoices/${invoiceId}/pay`, payload);
  return data;
}

export async function bulkChargeInvoices(invoiceIds: string[], amount: number): Promise<BulkActionResult> {
  const { data } = await apiClient.post<BulkActionResult>("/invoices/bulk/charge", {
    invoice_ids: invoiceIds,
    amount,
  });
  return data;
}

export async function listPaymentAccounts(): Promise<PaymentAccount[]> {
  const { data } = await apiClient.get<PaymentAccount[]>("/payment-accounts");
  return data;
}

export async function createPaymentAccount(name: string, kind = "other"): Promise<PaymentAccount> {
  const { data } = await apiClient.post<PaymentAccount>("/payment-accounts", { name, kind });
  return data;
}

export async function getBalanceByAccount(): Promise<AccountBalance[]> {
  const { data } = await apiClient.get<AccountBalance[]>("/billing/balance-by-account");
  return data;
}

export async function getBillingSettings(): Promise<BillingSettings> {
  const { data } = await apiClient.get<BillingSettings>("/billing-settings");
  return data;
}

export async function updateBillingSettings(
  payload: Partial<BillingSettings>,
): Promise<BillingSettings> {
  const { data } = await apiClient.patch<BillingSettings>("/billing-settings", payload);
  return data;
}

export async function listPaymentReports(status?: PaymentReportStatus): Promise<PaymentReport[]> {
  const { data } = await apiClient.get<PaymentReport[]>("/payment-reports", {
    params: status ? { status_filter: status } : undefined,
  });
  return data;
}

export async function confirmPaymentReport(id: string): Promise<Invoice> {
  const { data } = await apiClient.post<Invoice>(`/payment-reports/${id}/confirm`);
  return data;
}

export async function rejectPaymentReport(id: string): Promise<PaymentReport> {
  const { data } = await apiClient.post<PaymentReport>(`/payment-reports/${id}/reject`);
  return data;
}
