import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  bulkReactivateClients,
  bulkSuspendClients,
  createClient,
  deleteClient,
  listClients,
  reactivateClient,
  suspendClient,
  updateClient,
} from "../api/clients";
import { provisionClientQos, removeClientQos } from "../api/qos";
import { listPlans } from "../api/plans";
import { listDevices } from "../api/devices";
import { listZones } from "../api/zones";
import type { Client, ClientInput } from "../api/types";
import Field from "../components/Field";
import SortableHeader from "../components/SortableHeader";
import { compareIp, compareText } from "../utils/sort";

const emptyForm: ClientInput = {
  full_name: "",
  identification: "",
  email: "",
  phone: "",
  address: "",
  latitude: null,
  longitude: null,
  plan_id: null,
  mikrotik_device_id: null,
  ip_address: "",
  public_ip_address: "",
  public_ip_provider_interface: "",
  public_ip_lan_interface: "",
  zone_id: null,
};

export default function Clients() {
  const queryClient = useQueryClient();
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: listPlans });
  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: listDevices });
  const { data: zones = [] } = useQuery({ queryKey: ["zones"], queryFn: listZones });
  const [form, setForm] = useState<ClientInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [sort, setSort] = useState<{ field: SortField; dir: "asc" | "desc" }>({
    field: "full_name",
    dir: "asc",
  });
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const sortedClients = useMemo(() => {
    const value = (client: (typeof clients)[number]): string => {
      switch (sort.field) {
        case "plan":
          return planName(client.plan_id);
        case "status":
          return client.status;
        case "is_online":
          return client.is_online ? "1" : "0";
        case "ip_address":
          return client.ip_address ?? "";
        default:
          return client.full_name;
      }
    };
    const compare = sort.field === "ip_address" ? compareIp : compareText;
    const sorted = [...clients].sort((a, b) => compare(value(a), value(b)));
    return sort.dir === "asc" ? sorted : sorted.reverse();
  }, [clients, sort, plans]);

  function toggleSort(field: SortField) {
    setSort((prev) =>
      prev.field === field ? { field, dir: prev.dir === "asc" ? "desc" : "asc" } : { field, dir: "asc" },
    );
  }

  const createMutation = useMutation({
    mutationFn: createClient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      closeForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ClientInput }) => updateClient(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      closeForm();
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      alert("QoS aplicado: el cliente ya está en el address-list de su plan.");
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo aplicar el QoS."),
  });

  const removeQosMutation = useMutation({
    mutationFn: removeClientQos,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      alert("QoS quitado: el cliente ya no está en el address-list de su plan.");
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo quitar el QoS."),
  });

  const bulkSuspendMutation = useMutation({
    mutationFn: bulkSuspendClients,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setSelected(new Set());
      reportBulkFailures(result, "suspender");
    },
  });

  const bulkReactivateMutation = useMutation({
    mutationFn: bulkReactivateClients,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      setSelected(new Set());
      reportBulkFailures(result, "reactivar");
    },
  });

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAllVisible() {
    setSelected((prev) =>
      prev.size === sortedClients.length ? new Set() : new Set(sortedClients.map((c) => c.id)),
    );
  }

  function closeForm() {
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(false);
  }

  function startEdit(client: Client) {
    setForm({
      full_name: client.full_name,
      identification: client.identification ?? "",
      email: client.email ?? "",
      phone: client.phone ?? "",
      address: client.address ?? "",
      latitude: client.latitude,
      longitude: client.longitude,
      plan_id: client.plan_id,
      mikrotik_device_id: client.mikrotik_device_id,
      ip_address: client.ip_address ?? "",
      public_ip_address: client.public_ip_address ?? "",
      public_ip_provider_interface: client.public_ip_provider_interface ?? "",
      public_ip_lan_interface: client.public_ip_lan_interface ?? "",
      zone_id: client.zone_id,
    });
    setEditingId(client.id);
    setShowForm(true);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (editingId) {
      updateMutation.mutate({ id: editingId, payload: form });
    } else {
      createMutation.mutate(form);
    }
  }

  function planName(id: string | null) {
    return plans.find((p) => p.id === id)?.name ?? "—";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Clientes</h1>
        <button
          onClick={() => (showForm ? closeForm() : setShowForm(true))}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2"
        >
          {showForm ? "Cancelar" : "Nuevo cliente"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <h2 className="col-span-2 text-sm font-medium text-slate-600 -mb-2">
            {editingId ? "Editar cliente" : "Nuevo cliente"}
          </h2>
          <Field label="Nombre completo">
            <input
              required
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Identificación">
            <input
              value={form.identification ?? ""}
              onChange={(e) => setForm({ ...form, identification: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Correo">
            <input
              value={form.email ?? ""}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Teléfono">
            <input
              value={form.phone ?? ""}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Dirección">
            <input
              value={form.address ?? ""}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field
            label="Latitud / Longitud (para el mapa, opcional)"
            hint="Podés copiarlas desde Google Maps: click derecho sobre el punto → copiar coordenadas."
          >
            <div className="flex gap-2">
              <input
                type="number"
                step="any"
                placeholder="Latitud"
                value={form.latitude ?? ""}
                onChange={(e) => setForm({ ...form, latitude: e.target.value ? Number(e.target.value) : null })}
                className="border rounded px-3 py-2 text-sm w-full"
              />
              <input
                type="number"
                step="any"
                placeholder="Longitud"
                value={form.longitude ?? ""}
                onChange={(e) => setForm({ ...form, longitude: e.target.value ? Number(e.target.value) : null })}
                className="border rounded px-3 py-2 text-sm w-full"
              />
            </div>
          </Field>
          <Field label="IP asignada">
            <input
              value={form.ip_address ?? ""}
              onChange={(e) => setForm({ ...form, ip_address: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="IP pública (proxy-ARP, opcional)">
            <input
              value={form.public_ip_address ?? ""}
              onChange={(e) => setForm({ ...form, public_ip_address: e.target.value })}
              placeholder="ej. 190.71.83.43"
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Interfaz del proveedor (bloque público)">
            <input
              value={form.public_ip_provider_interface ?? ""}
              onChange={(e) => setForm({ ...form, public_ip_provider_interface: e.target.value })}
              placeholder="ej. eth10 / sfp-sfpplus1"
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Interfaz LAN del cliente">
            <input
              value={form.public_ip_lan_interface ?? ""}
              onChange={(e) => setForm({ ...form, public_ip_lan_interface: e.target.value })}
              placeholder="ej. eth0 / ether2"
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Plan">
            <select
              value={form.plan_id ?? ""}
              onChange={(e) => setForm({ ...form, plan_id: e.target.value || null })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="">Sin plan</option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Equipo Mikrotik">
            <select
              value={form.mikrotik_device_id ?? ""}
              onChange={(e) => setForm({ ...form, mikrotik_device_id: e.target.value || null })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="">Sin equipo asignado</option>
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Zona">
            <select
              value={form.zone_id ?? ""}
              onChange={(e) => setForm({ ...form, zone_id: e.target.value || null })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="">Sin zona</option>
              {zones.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            {editingId ? "Actualizar cliente" : "Guardar cliente"}
          </button>
        </form>
      )}

      {selected.size > 0 && (
        <div className="bg-slate-900 text-white text-sm rounded-lg px-4 py-2 flex items-center gap-4">
          <span>{selected.size} seleccionados</span>
          <button
            onClick={() => bulkSuspendMutation.mutate([...selected])}
            disabled={bulkSuspendMutation.isPending}
            className="text-amber-300 hover:underline disabled:opacity-50"
          >
            Suspender seleccionados
          </button>
          <button
            onClick={() => bulkReactivateMutation.mutate([...selected])}
            disabled={bulkReactivateMutation.isPending}
            className="text-green-300 hover:underline disabled:opacity-50"
          >
            Reactivar seleccionados
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
                  checked={selected.size > 0 && selected.size === sortedClients.length}
                  onChange={toggleSelectAllVisible}
                />
              </th>
              <SortableHeader field="full_name" label="Nombre" sort={sort} onClick={toggleSort} />
              <SortableHeader field="ip_address" label="IP" sort={sort} onClick={toggleSort} />
              <SortableHeader field="plan" label="Plan" sort={sort} onClick={toggleSort} />
              <SortableHeader field="is_online" label="Conexión" sort={sort} onClick={toggleSort} />
              <SortableHeader field="status" label="Estado" sort={sort} onClick={toggleSort} />
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {sortedClients.map((client) => (
              <tr key={client.id} className="border-t">
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(client.id)}
                    onChange={() => toggleSelected(client.id)}
                  />
                </td>
                <td className="px-4 py-2">
                  {client.full_name}
                  <div className="text-xs text-slate-400">{client.email}</div>
                </td>
                <td className="px-4 py-2 font-mono text-xs">{client.ip_address ?? "—"}</td>
                <td className="px-4 py-2">{planName(client.plan_id)}</td>
                <td className="px-4 py-2">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs ${
                      client.is_online
                        ? "bg-green-100 text-green-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                    title={
                      client.last_seen_at
                        ? `Visto por última vez: ${new Date(client.last_seen_at).toLocaleString()}`
                        : "Sin datos de conexión todavía"
                    }
                  >
                    <span
                      className={`inline-block h-1.5 w-1.5 rounded-full ${
                        client.is_online ? "bg-green-500" : "bg-slate-400"
                      }`}
                    />
                    {client.is_online ? "Conectado" : "Desconectado"}
                  </span>
                </td>
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
                  <button onClick={() => startEdit(client)} className="text-xs text-blue-600 hover:underline">
                    Editar
                  </button>
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
                <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
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

type SortField = "full_name" | "ip_address" | "plan" | "status" | "is_online";

function reportBulkFailures(result: { results: { id: string; ok: boolean; detail: string | null }[] }, action: string) {
  const failures = result.results.filter((r) => !r.ok);
  if (failures.length === 0) return;
  const lines = failures.map((f) => `${f.id}: ${f.detail ?? "error desconocido"}`);
  alert(`No se pudo ${action} ${failures.length} de ${result.results.length}:\n${lines.join("\n")}`);
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
