import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listInvoices, payInvoice } from "../api/billing";
import { listClients } from "../api/clients";

export default function Billing() {
  const queryClient = useQueryClient();
  const { data: invoices = [] } = useQuery({ queryKey: ["invoices"], queryFn: listInvoices });
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const [payingId, setPayingId] = useState<string | null>(null);

  const payMutation = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount: number }) =>
      payInvoice(id, { amount, method: "manual" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      setPayingId(null);
    },
  });

  function clientName(id: string) {
    return clients.find((c) => c.id === id)?.full_name ?? id;
  }

  function handlePay(invoiceId: string, amount: number) {
    setPayingId(invoiceId);
    payMutation.mutate({ id: invoiceId, amount });
  }

  const statusStyles: Record<string, string> = {
    pending: "bg-slate-100 text-slate-600",
    paid: "bg-green-100 text-green-700",
    overdue: "bg-red-100 text-red-700",
    cancelled: "bg-slate-100 text-slate-400",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Facturación</h1>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Cliente</th>
              <th className="px-4 py-2">Período</th>
              <th className="px-4 py-2">Vencimiento</th>
              <th className="px-4 py-2">Monto</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id} className="border-t">
                <td className="px-4 py-2">{clientName(inv.client_id)}</td>
                <td className="px-4 py-2">
                  {inv.period_start} → {inv.period_end}
                </td>
                <td className="px-4 py-2">{inv.due_date}</td>
                <td className="px-4 py-2">${Number(inv.amount).toFixed(2)}</td>
                <td className="px-4 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${statusStyles[inv.status]}`}>
                    {inv.status}
                  </span>
                </td>
                <td className="px-4 py-2">
                  {inv.status !== "paid" && (
                    <button
                      disabled={payingId === inv.id}
                      onClick={() => handlePay(inv.id, Number(inv.amount))}
                      className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                    >
                      Marcar pagada
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Aún no hay facturas. Se generan automáticamente cada mes para clientes activos con plan.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
