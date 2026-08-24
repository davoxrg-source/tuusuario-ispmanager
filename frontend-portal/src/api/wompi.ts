import { apiClient } from "./client";

export interface CheckoutUrlResult {
  checkout_url: string;
  reference: string;
}

export async function createCheckoutUrl(invoiceId: string): Promise<CheckoutUrlResult> {
  const { data } = await apiClient.post<CheckoutUrlResult>(`/invoices/${invoiceId}/checkout-url`);
  return data;
}
