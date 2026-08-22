import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createClient,
  deleteClient,
  listClients,
  reactivateClient,
  suspendClient,
} from "../api/clients";
import { provisionClientQos, removeClientQos } from "../api/qos";
import { listPlans } from "../api/plans";
import { listDevices } from "../api/devices";
import type { ClientInput } from "../api/types";

const emptyForm: ClientInput = {
  full_name: "",
  email: "",
  phone: "",
  plan_id: null,
  mikrotik_device_id: null,
  pppoe_username: "",
  pppoe_password: "",
  ip_address: "",
};

export default function Clients() {
  const queryClient = useQueryClient();
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: listPlans });
  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: listDevices });
  const [form, setForm] = useState<ClientInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);

  const createMutation = useMutation({
    mutationFn: createClient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setForm(emptyForm);
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteClient,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clients"] }),
  });

  const suspendMutation = useMutation({
    mutationFn: suspendClient,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clients"] }),
  });

  const reactivateMutation = useMutation({
    mutationFn: reactivateClient,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clients"] }),
  });

  const provisionQosMutation = useMutation({
    mutationFn: provisionClientQos,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clients"] }),
    onError: (err) =>
      alert(axiosErrorMessage(err) ?? "No se pudo aplicar el QoS. ¿El plan ya tiene su infraestructura creada en el equipo (pestaña QoS del equipo)?"),
  });

  const removeQosMutation = useMutation({
    mutationFn: removeClientQos,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clients"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo quitar el QoS."),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate(form);
  }

  function planName(id: string | null) {
    return plans.find((p) => p.id === id)?.name ?? "—";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Clientes</h1>
        <button onClick={() => setShowForm((s) => !s)} className="bg-slate-900 text-white text-sm rounded px-4 py-2">
          {showForm ? "Cancelar" : "Nuevo cliente"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <input
            required
            placeholder="Nombre completo"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            placeholder="Correo"
            value={form.email ?? ""}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            placeholder="Teléfono"
            value={form.phone ?? ""}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <select
            value={form.plan_id ?? ""}
            onChange={(e) => setForm({ ...form, plan_id: e.target.value || null })}
            className="border rounded px-3 py-2 text-sm"
          >
            <option value="">Sin plan</option>
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name}
              </option>
            ))}
          </select>
          <select
            value={form.mikrotik_device_id ?? ""}
            onChange={(e) => setForm({ ...form, mikrotik_device_id: e.target.value || null })}
            className="border rounded px-3 py-2 text-sm"
          >
            <option value="">Sin equipo asignado</option>
            {devices.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name}
              </option>
            ))}
          </select>
          <input
            placeholder="IP asignada"
            value={form.ip_address ?? ""}
            onChange={(e) => setForm({ ...form, ip_address: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            placeholder="Usuario PPPoE"
            value={form.pppoe_username ?? ""}
            onChange={(e) => setForm({ ...form, pppoe_username: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            type="password"
            placeholder="Contraseña PPPoE"
            value={form.pppoe_password ?? ""}
            onChange={(e) => setForm({ ...form, pppoe_password: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            Guardar cliente
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Nombre</th>
              <th className="px-4 py-2">Plan</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => (
              <tr key={client.id} className="border-t">
                <td className="px-4 py-2">
                  {client.full_name}
                  <div className="text-xs text-slate-400">{client.email}</div>
                </td>
                <td className="px-4 py-2">{planName(client.plan_id)}</td>
                <td className="px-4 py-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                      client.status === "active"
                        ? "bg-green-100 text-green-700"
                        : client.status === "suspended"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {client.status}
                  </span>
                </td>
                <td className="px-4 py-2 space-x-2">
                  {client.status === "active" ? (
                    <button
                      onClick={() => suspendMutation.mutate(client.id)}
                      className="text-xs text-amber-600 hover:underline"
                    >
                      Suspender
                    </button>
                  ) : (
                    <button
                      onClick={() => reactivateMutation.mutate(client.id)}
                      className="text-xs text-green-600 hover:underline"
                    >
                      Reactivar
                    </button>
                  )}
                  <button
                    onClick={() => deleteMutation.mutate(client.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Eliminar
                  </button>
                  <button
                    onClick={() => provisionQosMutation.mutate(client.id)}
                    disabled={!client.plan_id || !client.ip_address || !client.mikrotik_device_id}
                    className="text-xs text-blue-600 hover:underline disabled:opacity-40 disabled:no-underline"
                    title={
                      !client.plan_id || !client.ip_address || !client.mikrotik_device_id
                        ? "Necesita plan, IP y equipo asignados"
                        : "Agrega la IP del cliente al address-list de su plan (requiere que el plan ya tenga su QoS creado en el equipo)"
                    }
                  >
                    Aplicar QoS
                  </button>
                  <button
                    onClick={() => removeQosMutation.mutate(client.id)}
                    disabled={!client.plan_id || !client.ip_address}
                    className="text-xs text-slate-500 hover:underline disabled:opacity-40 disabled:no-underline"
                  >
                    Quitar QoS
                  </button>
                </td>
              </tr>
            ))}
            {clients.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                  Aún no hay clientes.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function axiosErrorMessage(err: unknown): string | null {
  if (typeof err === "object" && err !== null && "response" in err) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0 && typeof detail[0]?.msg === "string") {
      return detail[0].msg;
    }
  }
  return null;
}
