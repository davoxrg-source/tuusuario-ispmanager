import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createZone, deleteZone, listZones, updateZone } from "../api/zones";
import type { Zone, ZoneInput } from "../api/types";
import Field from "../components/Field";

const emptyForm: ZoneInput = { name: "", description: "" };

export default function Zones() {
  const queryClient = useQueryClient();
  const { data: zones = [] } = useQuery({ queryKey: ["zones"], queryFn: listZones });
  const [form, setForm] = useState<ZoneInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: createZone,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zones"] });
      closeForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ZoneInput }) => updateZone(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["zones"] });
      closeForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteZone,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["zones"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo borrar la zona."),
  });

  function closeForm() {
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(false);
  }

  function startEdit(zone: Zone) {
    setForm({ name: zone.name, description: zone.description ?? "" });
    setEditingId(zone.id);
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Zonas</h1>
        <button
          onClick={() => (showForm ? closeForm() : setShowForm(true))}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2"
        >
          {showForm ? "Cancelar" : "Nueva zona"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <h2 className="col-span-2 text-sm font-medium text-slate-600 -mb-2">
            {editingId ? "Editar zona" : "Nueva zona"}
          </h2>
          <Field label="Nombre">
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="ej. ZONA_DIA_1"
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Descripción (opcional)">
            <input
              value={form.description ?? ""}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            {editingId ? "Actualizar zona" : "Guardar zona"}
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Nombre</th>
              <th className="px-4 py-2">Descripción</th>
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {zones.map((zone) => (
              <tr key={zone.id} className="border-t">
                <td className="px-4 py-2 font-medium">{zone.name}</td>
                <td className="px-4 py-2 text-slate-500">{zone.description ?? "—"}</td>
                <td className="px-4 py-2 space-x-2">
                  <button onClick={() => startEdit(zone)} className="text-xs text-blue-600 hover:underline">
                    Editar
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(zone.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
            {zones.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400">
                  Aún no hay zonas.
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
