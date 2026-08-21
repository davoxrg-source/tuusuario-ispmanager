import { apiClient } from "./client";
import type { Invoice } from "./types";

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
}

export async function payInvoice(invoiceId: string, payload: PaymentInput): Promise<Invoice> {
  const { data } = await apiClient.post<Invoice>(`/invoices/${invoiceId}/pay`, payload);
  return data;
}
