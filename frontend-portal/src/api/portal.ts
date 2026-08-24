import { apiClient } from "./client";
import type {
  ClientProfile,
  Invoice,
  PaymentReport,
  PaymentReportInput,
  ProfileUpdateInput,
  Ticket,
  TicketInput,
  TicketReply,
} from "./types";

export async function listMyInvoices(): Promise<Invoice[]> {
  const { data } = await apiClient.get<Invoice[]>("/invoices");
  return data;
}

export async function reportPayment(payload: PaymentReportInput): Promise<PaymentReport> {
  const { data } = await apiClient.post<PaymentReport>("/payment-reports", payload);
  return data;
}

export async function listMyTickets(): Promise<Ticket[]> {
  const { data } = await apiClient.get<Ticket[]>("/tickets");
  return data;
}

export async function createMyTicket(payload: TicketInput): Promise<Ticket> {
  const { data } = await apiClient.post<Ticket>("/tickets", payload);
  return data;
}

export async function getMyTicket(id: string): Promise<Ticket> {
  const { data } = await apiClient.get<Ticket>(`/tickets/${id}`);
  return data;
}

export async function listMyTicketReplies(ticketId: string): Promise<TicketReply[]> {
  const { data } = await apiClient.get<TicketReply[]>(`/tickets/${ticketId}/replies`);
  return data;
}

export async function replyToMyTicket(ticketId: string, body: string): Promise<TicketReply> {
  const { data } = await apiClient.post<TicketReply>(`/tickets/${ticketId}/reply`, { body });
  return data;
}

export async function updateMyProfile(payload: ProfileUpdateInput): Promise<ClientProfile> {
  const { data } = await apiClient.patch<ClientProfile>("/profile", payload);
  return data;
}
