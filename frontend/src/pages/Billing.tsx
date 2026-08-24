import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  bulkChargeInvoices,
  getBalanceByAccount,
  listInvoices,
  listPaymentAccounts,
  payInvoice,
} from "../api/billing";
import { listClients } from "../api/clients";

export default function Billing() {
  const queryClient = useQueryClient();
  const { data: invoices = [] } = useQuery({ queryKey: ["invoices"], queryFn: listInvoices });
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: accounts = [] } = useQuery({
    queryKey: ["payment-accounts"],
    queryFn: listPaymentAccounts,
  });
  const { data: balances = [] } = useQuery({
    queryKey: ["balance-by-account"],
    queryFn: getBalanceByAccount,
  });
  const [payingId, setPayingId] = useState<string | null>(null);
  const [accountByInvoice, setAccountByInvoice] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [chargeAmount, setChargeAmount] = useState("");

  const payMutation = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount: number }) =>
      payInvoice(id, { amount, method: "manual", payment_account_id: accountByInvoice[id] || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      queryClient.invalidateQueries({ queryKey: ["balance-by-account"] });
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setPayingId(null);
    },
  });

  const bulkChargeMutation = useMutation({
    mutationFn: () => bulkChargeInvoices([...selected], Number(chargeAmount)),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      const failures = result.results.filter((r) => !r.ok);
      setSelected(new Set());
      setChargeAmount("");
      if (failures.length > 0) {
        alert(
          `No se pudo aplicar el cargo a ${failures.length} de ${result.results.length}:\n` +
            failures.map((f) => `${f.id}: ${f.detail ?? "error desconocido"}`).join("\n"),
        );
      }
    },
  });

  function clientName(id: string) {
    return clients.find((c) => c.id === id)?.full_name ?? id;
  }

  function handlePay(invoiceId: string, amount: number) {
    setPayingId(invoiceId);
    payMutation.mutate({ id: invoiceId, amount });
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
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

      {balances.length > 0 && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-medium text-slate-600 mb-3">Saldo por cuenta</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {balances.map((b) => (
              <div key={b.id} className="border rounded p-3">
                <p className="text-xs text-slate-500">{b.name}</p>
                <p className="text-lg font-semibold text-slate-800">${b.total.toFixed(2)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {selected.size > 0 && (
        <div className="bg-slate-900 text-white text-sm rounded-lg px-4 py-2 flex items-center gap-4">
          <span>{selected.size} seleccionadas</span>
          <input
            type="number"
            step="0.01"
            placeholder="Monto del cargo"
            value={chargeAmount}
            onChange={(e) => setChargeAmount(e.target.value)}
            className="text-slate-900 rounded px-2 py-1 text-sm w-32"
          />
          <button
            onClick={() => bulkChargeMutation.mutate()}
            disabled={bulkChargeMutation.isPending || !chargeAmount || Number(chargeAmount) <= 0}
            className="text-blue-300 hover:underline disabled:opacity-50"
          >
            Aplicar cargo
          </button>
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 w-8">
                <input
                  type="checkbox"
                  checked={selected.size > 0 && selected.size === invoices.length}
                  onChange={() =>
                    setSelected((prev) =>
                      prev.size === invoices.length ? new Set() : new Set(invoices.map((i) => i.id)),
                    )
                  }
                />
              </th>
              <th className="px-4 py-2">Folio</th>
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
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(inv.id)}
                    onChange={() => toggleSelected(inv.id)}
                  />
                </td>
                <td className="px-4 py-2 font-mono text-xs">{inv.folio ?? "—"}</td>
                <td className="px-4 py-2">{clientName(inv.client_id)}</td>
                <td className="px-4 py-2">
                  {inv.period_start} → {inv.period_end}
                </td>
                <td className="px-4 py-2">{inv.due_date}</td>
                <td className="px-4 py-2">
                  ${Number(inv.amount).toFixed(2)}
                  {inv.late_fee_amount > 0 && (
                    <span className="text-xs text-red-500 ml-1">
                      (+${Number(inv.late_fee_amount).toFixed(2)} mora)
                    </span>
                  )}
                </td>
                <td className="px-4 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${statusStyles[inv.status]}`}>
                    {inv.status}
                  </span>
                </td>
                <td className="px-4 py-2">
                  {inv.status !== "paid" && (
                    <div className="flex items-center gap-2">
                      <select
                        value={accountByInvoice[inv.id] ?? ""}
                        onChange={(e) =>
                          setAccountByInvoice((prev) => ({ ...prev, [inv.id]: e.target.value }))
                        }
                        className="border rounded px-1 py-0.5 text-xs bg-white"
                      >
                        <option value="">Cuenta (opcional)</option>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name}
                          </option>
                        ))}
                      </select>
                      <button
                        disabled={payingId === inv.id}
                        onClick={() => handlePay(inv.id, Number(inv.amount))}
                        className="text-xs text-blue-600 hover:underline disabled:opacity-50"
                      >
                        Marcar pagada
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-slate-400">
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
