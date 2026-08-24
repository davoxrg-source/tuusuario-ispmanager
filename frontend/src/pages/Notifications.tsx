import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listNotifications } from "../api/notifications";
import { listClients } from "../api/clients";
import type { NotificationChannel, NotificationStatus } from "../api/types";

const channelLabels: Record<NotificationChannel, string> = {
  email: "Correo",
  push: "Push",
};

const statusStyles: Record<NotificationStatus, string> = {
  sent: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

const eventLabels: Record<string, string> = {
  portal_activated: "Portal activado",
  payment_confirmed: "Pago confirmado",
  payment_rejected: "Pago rechazado",
  ticket_reply: "Respuesta a ticket",
  invoice_due_reminder: "Recordatorio de vencimiento",
};

export default function Notifications() {
  const [clientId, setClientId] = useState("");
  const [statusFilter, setStatusFilter] = useState<NotificationStatus | "">("");
  const [channel, setChannel] = useState<NotificationChannel | "">("");

  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: notifications = [], isLoading } = useQuery({
    queryKey: ["notifications", clientId, statusFilter, channel],
    queryFn: () =>
      listNotifications({
        client_id: clientId || undefined,
        status_filter: statusFilter || undefined,
        channel: channel || undefined,
      }),
  });

  function clientName(id: string) {
    return clients.find((c) => c.id === id)?.full_name ?? id;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Notificaciones</h1>

      <div className="bg-white rounded-lg shadow p-4 flex flex-wrap gap-3">
        <select
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="border rounded px-3 py-2 text-sm bg-white"
        >
          <option value="">Todos los clientes</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.full_name}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as NotificationStatus | "")}
          className="border rounded px-3 py-2 text-sm bg-white"
        >
          <option value="">Cualquier estado</option>
          <option value="sent">Enviada</option>
          <option value="failed">Fallida</option>
        </select>
        <select
          value={channel}
          onChange={(e) => setChannel(e.target.value as NotificationChannel | "")}
          className="border rounded px-3 py-2 text-sm bg-white"
        >
          <option value="">Cualquier canal</option>
          <option value="email">Correo</option>
          <option value="push">Push</option>
        </select>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Cliente</th>
              <th className="px-4 py-2">Evento</th>
              <th className="px-4 py-2">Canal</th>
              <th className="px-4 py-2">Destinatario</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2">Fecha</th>
            </tr>
          </thead>
          <tbody>
            {notifications.map((n) => (
              <tr key={n.id} className="border-t">
                <td className="px-4 py-2">{clientName(n.client_id)}</td>
                <td className="px-4 py-2">{eventLabels[n.event_type] ?? n.event_type}</td>
                <td className="px-4 py-2">{channelLabels[n.channel]}</td>
                <td className="px-4 py-2 font-mono text-xs truncate max-w-xs">{n.recipient}</td>
                <td className="px-4 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${statusStyles[n.status]}`}>
                    {n.status === "sent" ? "Enviada" : "Fallida"}
                  </span>
                  {n.error_message && (
                    <div className="text-xs text-slate-400 mt-0.5">{n.error_message}</div>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-500">{new Date(n.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {!isLoading && notifications.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Sin notificaciones todavía.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
