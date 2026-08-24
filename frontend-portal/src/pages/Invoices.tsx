import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { listMyInvoices, reportPayment } from "../api/portal";
import { createCheckoutUrl } from "../api/wompi";

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
  const [searchParams] = useSearchParams();
  const confirmingWompiInvoice = searchParams.get("wompi_id");

  const checkoutMutation = useMutation({
    mutationFn: createCheckoutUrl,
    onSuccess: (result) => {
      window.location.href = result.checkout_url;
    },
    onError: () => alert("No se pudo iniciar el pago en línea. Probá de nuevo en un momento."),
  });

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
      {confirmingWompiInvoice && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
          Estamos confirmando tu pago -- puede tardar un momento en reflejarse acá. Si no ves el cambio,
          actualizá la página en un rato.
        </div>
      )}
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

          {(inv.status === "pending" || inv.status === "overdue") && (
            <button
              onClick={() => checkoutMutation.mutate(inv.id)}
              disabled={checkoutMutation.isPending}
              className="w-full bg-slate-900 text-white text-sm rounded py-1.5 disabled:opacity-50"
            >
              Pagar en línea
            </button>
          )}

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
