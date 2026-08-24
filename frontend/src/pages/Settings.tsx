import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCurrentUser } from "../api/auth";
import { getBillingSettings, updateBillingSettings } from "../api/billing";
import type { BillingSettings } from "../api/types";
import Field from "../components/Field";

export default function Settings() {
  const { data: user } = useQuery({ queryKey: ["me"], queryFn: fetchCurrentUser });
  const queryClient = useQueryClient();
  const { data: billingSettings } = useQuery({
    queryKey: ["billing-settings"],
    queryFn: getBillingSettings,
  });
  const [form, setForm] = useState<BillingSettings | null>(null);

  useEffect(() => {
    if (billingSettings) setForm(billingSettings);
  }, [billingSettings]);

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<BillingSettings>) => updateBillingSettings(payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(["billing-settings"], updated);
      alert("Ajustes de facturación guardados.");
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (form) saveMutation.mutate(form);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Configuración</h1>
      <div className="bg-white rounded-lg shadow p-5 max-w-md">
        <h2 className="text-sm font-medium text-slate-600 mb-3">Sesión actual</h2>
        {user ? (
          <dl className="text-sm space-y-1">
            <div className="flex justify-between">
              <dt className="text-slate-500">Nombre</dt>
              <dd>{user.full_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Correo</dt>
              <dd>{user.email}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Rol</dt>
              <dd>{user.role}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-sm text-slate-400">Cargando...</p>
        )}
      </div>

      {form && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <h2 className="col-span-2 text-sm font-medium text-slate-600 -mb-2">Facturación</h2>

          <Field label="Días antes del vencimiento para generar factura">
            <input
              type="number"
              min={0}
              value={form.generate_invoice_days_before_due}
              onChange={(e) => setForm({ ...form, generate_invoice_days_before_due: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Días de gracia antes de suspender">
            <input
              type="number"
              min={0}
              value={form.suspend_days_after_due}
              onChange={(e) => setForm({ ...form, suspend_days_after_due: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>

          <Field label="Mora automática">
            <select
              value={form.late_fee_enabled ? "1" : "0"}
              onChange={(e) => setForm({ ...form, late_fee_enabled: e.target.value === "1" })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="0">Desactivada</option>
              <option value="1">Activada</option>
            </select>
          </Field>
          <Field label="Monto de mora">
            <input
              type="number"
              step="0.01"
              min={0}
              value={form.late_fee_amount}
              onChange={(e) => setForm({ ...form, late_fee_amount: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Hora del día para aplicar mora (0-23)">
            <input
              type="number"
              min={0}
              max={23}
              value={form.late_fee_apply_hour}
              onChange={(e) => setForm({ ...form, late_fee_apply_hour: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>

          <Field label="Prorrateo post-corte">
            <select
              value={form.proration_enabled ? "1" : "0"}
              onChange={(e) => setForm({ ...form, proration_enabled: e.target.value === "1" })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="0">Desactivado</option>
              <option value="1">Activado</option>
            </select>
          </Field>
          <Field label="Mínimo de días sin usar para prorratear">
            <input
              type="number"
              min={0}
              value={form.proration_min_days}
              onChange={(e) => setForm({ ...form, proration_min_days: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Aplicar el crédito de prorrateo a">
            <select
              value={form.proration_target}
              onChange={(e) =>
                setForm({ ...form, proration_target: e.target.value as BillingSettings["proration_target"] })
              }
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="current_invoice">La factura actual</option>
              <option value="next_invoice">La próxima factura</option>
            </select>
          </Field>

          <Field label="Cargo de reconexión">
            <select
              value={form.reconnection_fee_mode}
              onChange={(e) =>
                setForm({
                  ...form,
                  reconnection_fee_mode: e.target.value as BillingSettings["reconnection_fee_mode"],
                })
              }
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="off">No aplicar</option>
              <option value="on_suspend">Al suspender</option>
              <option value="on_next_invoice">En la próxima factura</option>
            </select>
          </Field>
          <Field label="Monto de reconexión">
            <input
              type="number"
              step="0.01"
              min={0}
              value={form.reconnection_fee_amount}
              onChange={(e) => setForm({ ...form, reconnection_fee_amount: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>

          <Field label="Prefijo de folio">
            <input
              value={form.invoice_folio_prefix}
              onChange={(e) => setForm({ ...form, invoice_folio_prefix: e.target.value })}
              placeholder="ej. F-"
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Próximo número de folio">
            <input
              type="number"
              min={1}
              value={form.invoice_folio_next_number}
              onChange={(e) => setForm({ ...form, invoice_folio_next_number: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>

          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            Guardar ajustes de facturación
          </button>
        </form>
      )}
    </div>
  );
}
