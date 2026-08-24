import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { listMyInvoices, reportPayment } from "../api/portal";

const statusStyles: Record<string, string> = {
  pending: "bg-slate-100 text-slate-600",
  paid: "bg-green-100 text-green-700",
  overdue: "bg-red-100 text-red-700",
  cancelled: "bg-slate-100 text-slate-400",
};

const statusLabels: Record<string, string> = {
  pending: "Pendiente",
  paid: "Pagada",
  overdue: "Vencida",
  cancelled: "Cancelada",
};

export default function Invoices() {
  const { data: invoices = [] } = useQuery({ queryKey: ["my-invoices"], queryFn: listMyInvoices });
  const [reportingId, setReportingId] = useState<string | null>(null);
  const [method, setMethod] = useState("");
  const [reference, setReference] = useState("");

  const reportMutation = useMutation({
    mutationFn: (invoiceId: string) =>
      reportPayment({
        invoice_id: invoiceId,
        amount: Number(invoices.find((i) => i.id === invoiceId)?.amount ?? 0),
        method,
        reference: reference || null,
      }),
    onSuccess: () => {
      setReportingId(null);
      setMethod("");
      setReference("");
      alert("Gracias -- tu pago fue reportado y va a ser verificado por el equipo.");
    },
  });

  function handleSubmit(e: FormEvent, invoiceId: string) {
    e.preventDefault();
    reportMutation.mutate(invoiceId);
  }

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-semibold text-slate-800">Mis facturas</h1>
      {invoices.map((inv) => (
        <div key={inv.id} className="bg-white rounded-lg shadow p-4 space-y-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-700">
                {inv.period_start} → {inv.period_end}
              </p>
              <p className="text-xs text-slate-400">Vence: {inv.due_date}</p>
            </div>
            <span className={`text-xs rounded-full px-2 py-0.5 ${statusStyles[inv.status]}`}>
              {statusLabels[inv.status]}
            </span>
          </div>
          <p className="text-lg font-semibold text-slate-800">
            ${Number(inv.amount).toFixed(2)}
            {inv.late_fee_amount > 0 && (
              <span className="text-xs text-red-500 ml-1">
                (+${Number(inv.late_fee_amount).toFixed(2)} mora)
              </span>
            )}
          </p>

          {(inv.status === "pending" || inv.status === "overdue") &&
            (reportingId === inv.id ? (
              <form onSubmit={(e) => handleSubmit(e, inv.id)} className="space-y-2 border-t pt-2">
                <input
                  required
                  placeholder="Método (ej. Nequi, transferencia)"
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                  className="w-full border rounded px-2 py-1.5 text-sm"
                />
                <input
                  placeholder="Referencia / comprobante (opcional)"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  className="w-full border rounded px-2 py-1.5 text-sm"
                />
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={reportMutation.isPending}
                    className="flex-1 bg-slate-900 text-white text-sm rounded py-1.5 disabled:opacity-50"
                  >
                    Enviar
                  </button>
                  <button
                    type="button"
                    onClick={() => setReportingId(null)}
                    className="text-sm text-slate-500"
                  >
                    Cancelar
                  </button>
                </div>
              </form>
            ) : (
              <button
                onClick={() => setReportingId(inv.id)}
                className="text-sm text-blue-600 hover:underline"
              >
                Ya pagué esta factura
              </button>
            ))}
        </div>
      ))}
      {invoices.length === 0 && <p className="text-sm text-slate-400">Todavía no tenés facturas.</p>}
    </div>
  );
}
