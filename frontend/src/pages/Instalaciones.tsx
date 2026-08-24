import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  calculateRouteDistance,
  createInstallation,
  deleteInstallation,
  listInstallations,
  updateInstallation,
} from "../api/installations";
import { listClients } from "../api/clients";
import { listStaffDirectory } from "../api/users";
import { fetchCurrentUser } from "../api/auth";
import type { Installation, InstallationInput, InstallationStatus } from "../api/types";
import Field from "../components/Field";

const emptyForm: InstallationInput = {
  client_id: "",
  assigned_technician_id: null,
  scheduled_date: new Date().toISOString().slice(0, 10),
  status: "scheduled",
  notes: "",
};

const statusLabels: Record<InstallationStatus, string> = {
  scheduled: "Programada",
  completed: "Completada",
  cancelled: "Cancelada",
};

const statusStyles: Record<InstallationStatus, string> = {
  scheduled: "bg-slate-100 text-slate-600",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

type DateFilter = "all" | "today" | "week";

export default function Instalaciones() {
  const queryClient = useQueryClient();
  const { data: installations = [] } = useQuery({
    queryKey: ["installations"],
    queryFn: listInstallations,
  });
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: technicians = [] } = useQuery({
    queryKey: ["staff-directory"],
    queryFn: listStaffDirectory,
  });
  const { data: currentUser } = useQuery({ queryKey: ["me"], queryFn: fetchCurrentUser });

  const [form, setForm] = useState<InstallationInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [dateFilter, setDateFilter] = useState<DateFilter>("all");
  const [onlyMine, setOnlyMine] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [routeResult, setRouteResult] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    const weekAhead = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);
    return installations.filter((i) => {
      if (dateFilter === "today" && i.scheduled_date !== today) return false;
      if (dateFilter === "week" && (i.scheduled_date < today || i.scheduled_date > weekAhead)) return false;
      if (onlyMine && i.assigned_technician_id !== currentUser?.id) return false;
      return true;
    });
  }, [installations, dateFilter, onlyMine, currentUser]);

  const createMutation = useMutation({
    mutationFn: createInstallation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["installations"] });
      closeForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: InstallationInput }) =>
      updateInstallation(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["installations"] });
      closeForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteInstallation,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["installations"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo borrar la instalación."),
  });

  const routeMutation = useMutation({
    mutationFn: () => calculateRouteDistance([...selected]),
    onSuccess: (result) => {
      setRouteResult(`Distancia total de la ruta: ${result.total_km.toFixed(2)} km`);
    },
    onError: (err) => {
      setRouteResult(null);
      alert(axiosErrorMessage(err) ?? "No se pudo calcular la distancia.");
    },
  });

  function closeForm() {
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(false);
  }

  function startEdit(installation: Installation) {
    setForm({
      client_id: installation.client_id,
      assigned_technician_id: installation.assigned_technician_id,
      scheduled_date: installation.scheduled_date,
      status: installation.status,
      notes: installation.notes ?? "",
    });
    setEditingId(installation.id);
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

  function toggleSelected(id: string) {
    setRouteResult(null);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function clientName(id: string) {
    return clients.find((c) => c.id === id)?.full_name ?? id;
  }

  function technicianName(id: string | null) {
    return technicians.find((t) => t.id === id)?.full_name ?? "Sin asignar";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Instalaciones</h1>
        <button
          onClick={() => (showForm ? closeForm() : setShowForm(true))}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2"
        >
          {showForm ? "Cancelar" : "Nueva instalación"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <h2 className="col-span-2 text-sm font-medium text-slate-600 -mb-2">
            {editingId ? "Editar instalación" : "Nueva instalación"}
          </h2>
          <Field label="Cliente">
            <select
              required
              value={form.client_id}
              onChange={(e) => setForm({ ...form, client_id: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="">Seleccionar...</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Técnico (opcional)">
            <select
              value={form.assigned_technician_id ?? ""}
              onChange={(e) => setForm({ ...form, assigned_technician_id: e.target.value || null })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="">Sin asignar</option>
              {technicians.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Fecha programada">
            <input
              required
              type="date"
              value={form.scheduled_date}
              onChange={(e) => setForm({ ...form, scheduled_date: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Estado">
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as InstallationStatus })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="scheduled">Programada</option>
              <option value="completed">Completada</option>
              <option value="cancelled">Cancelada</option>
            </select>
          </Field>
          <Field label="Notas (opcional)">
            <input
              value={form.notes ?? ""}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            {editingId ? "Actualizar instalación" : "Guardar instalación"}
          </button>
        </form>
      )}

      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          {(["all", "today", "week"] as DateFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setDateFilter(f)}
              className={`px-3 py-1.5 rounded text-xs ${
                dateFilter === f ? "bg-slate-900 text-white" : "bg-white text-slate-600 border"
              }`}
            >
              {f === "all" ? "Todas" : f === "today" ? "Hoy" : "Esta semana"}
            </button>
          ))}
          <label className="flex items-center gap-1.5 text-xs text-slate-600 ml-2">
            <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
            Solo mías
          </label>
        </div>

        {selected.size > 1 && (
          <div className="flex items-center gap-2 text-sm">
            <button
              onClick={() => routeMutation.mutate()}
              disabled={routeMutation.isPending}
              className="text-xs text-blue-600 hover:underline disabled:opacity-50"
            >
              Calcular distancia ({selected.size} seleccionadas)
            </button>
            {routeResult && <span className="text-xs text-slate-500">{routeResult}</span>}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 w-8"></th>
              <th className="px-4 py-2">Cliente</th>
              <th className="px-4 py-2">Técnico</th>
              <th className="px-4 py-2">Fecha</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2">Notas</th>
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((installation) => (
              <tr key={installation.id} className="border-t">
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(installation.id)}
                    onChange={() => toggleSelected(installation.id)}
                  />
                </td>
                <td className="px-4 py-2">{clientName(installation.client_id)}</td>
                <td className="px-4 py-2">{technicianName(installation.assigned_technician_id)}</td>
                <td className="px-4 py-2">{installation.scheduled_date}</td>
                <td className="px-4 py-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs ${statusStyles[installation.status]}`}
                  >
                    {statusLabels[installation.status]}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-500">{installation.notes ?? "—"}</td>
                <td className="px-4 py-2 space-x-2">
                  <button onClick={() => startEdit(installation)} className="text-xs text-blue-600 hover:underline">
                    Editar
                  </button>
                  <Link
                    to={`/instalaciones/${installation.id}/orden`}
                    target="_blank"
                    className="text-xs text-slate-600 hover:underline"
                  >
                    Orden de trabajo
                  </Link>
                  <button
                    onClick={() => deleteMutation.mutate(installation.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                  Ninguna instalación coincide con el filtro.
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
  }
  return null;
}
