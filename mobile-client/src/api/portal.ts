import { apiClient } from "./client";
import type { CheckoutUrlRead, Invoice, PaymentReportInput } from "./types";

export async function listMyInvoices(): Promise<Invoice[]> {
  const { data } = await apiClient.get<Invoice[]>("/invoices");
  return data;
}

export async function reportPayment(payload: PaymentReportInput): Promise<void> {
  await apiClient.post("/payment-reports", payload);
}

export async function createCheckoutUrl(invoiceId: string): Promise<CheckoutUrlRead> {
  const { data } = await apiClient.post<CheckoutUrlRead>(`/invoices/${invoiceId}/checkout-url`);
  return data;
}
