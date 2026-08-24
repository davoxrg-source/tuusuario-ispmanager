import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createApiKey, listApiKeys, revokeApiKey } from "../api/apiKeys";
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

  const { data: apiKeys = [] } = useQuery({
    queryKey: ["api-keys"],
    queryFn: listApiKeys,
    enabled: user?.role === "admin",
  });
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);

  const createKeyMutation = useMutation({
    mutationFn: createApiKey,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setGeneratedKey(result.key);
      setNewKeyName("");
    },
  });

  const revokeKeyMutation = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  function handleCreateKey(e: FormEvent) {
    e.preventDefault();
    setGeneratedKey(null);
    createKeyMutation.mutate(newKeyName);
  }

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

          <Field
            label="Recordatorio de pago antes del vencimiento"
            hint="Manda un aviso por correo/push (ver Notificaciones) cuando falten los días indicados para el vencimiento -- requiere SMTP configurado en el servidor para que el correo salga de verdad."
          >
            <select
              value={form.payment_reminder_enabled ? "1" : "0"}
              onChange={(e) => setForm({ ...form, payment_reminder_enabled: e.target.value === "1" })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="0">Desactivado</option>
              <option value="1">Activado</option>
            </select>
          </Field>
          <Field label="Días antes del vencimiento para recordar">
            <input
              type="number"
              min={0}
              value={form.payment_reminder_days_before_due}
              onChange={(e) =>
                setForm({ ...form, payment_reminder_days_before_due: Number(e.target.value) })
              }
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

      {user?.role === "admin" && (
        <div className="bg-white rounded-lg shadow p-5 max-w-2xl">
          <h2 className="text-sm font-medium text-slate-600 mb-1">Claves de API</h2>
          <p className="text-xs text-slate-400 mb-3">
            Para integraciones externas (solo lectura: clientes, facturas, planes) -- ver{" "}
            <code className="bg-slate-100 px-1 rounded">/api/v1</code> en la documentación de la API.
          </p>

          <form onSubmit={handleCreateKey} className="flex gap-2 mb-3">
            <input
              required
              placeholder="Nombre (ej. Contabilidad externa)"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              className="flex-1 border rounded px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={createKeyMutation.isPending}
              className="bg-slate-900 text-white text-sm rounded px-4 disabled:opacity-50"
            >
              Generar
            </button>
          </form>

          {generatedKey && (
            <div className="bg-amber-50 border border-amber-200 rounded p-3 mb-3 space-y-1">
              <p className="text-xs text-amber-700">
                Copiá esta clave ahora -- no se puede volver a ver.
              </p>
              <p className="font-mono text-sm break-all">{generatedKey}</p>
            </div>
          )}

          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">Nombre</th>
                <th className="py-1">Prefijo</th>
                <th className="py-1">Último uso</th>
                <th className="py-1">Estado</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {apiKeys.map((k) => (
                <tr key={k.id} className="border-t">
                  <td className="py-1">{k.name}</td>
                  <td className="py-1 font-mono text-xs">{k.key_prefix}…</td>
                  <td className="py-1 text-slate-500">
                    {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "Nunca"}
                  </td>
                  <td className="py-1">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                        k.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-400"
                      }`}
                    >
                      {k.is_active ? "Activa" : "Revocada"}
                    </span>
                  </td>
                  <td className="py-1">
                    {k.is_active && (
                      <button
                        onClick={() => revokeKeyMutation.mutate(k.id)}
                        disabled={revokeKeyMutation.isPending}
                        className="text-xs text-red-600 hover:underline disabled:opacity-50"
                      >
                        Revocar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {apiKeys.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-slate-400">
                    Todavía no hay claves de API.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
