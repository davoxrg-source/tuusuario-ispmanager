import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createPlan, deletePlan, listPlans, updatePlan, type PlanInput } from "../api/plans";
import type { Plan } from "../api/types";
import Field from "../components/Field";
import SortableHeader from "../components/SortableHeader";
import { compareNumber, compareText } from "../utils/sort";

type SortField = "name" | "speed" | "floor" | "price";

const emptyForm: PlanInput = {
  name: "",
  download_speed_mbps: 10,
  upload_speed_mbps: 5,
  price: 0,
  currency: "USD",
  guaranteed_floor_percent: 9,
};

export default function Plans() {
  const queryClient = useQueryClient();
  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: listPlans });
  const [form, setForm] = useState<PlanInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [sort, setSort] = useState<{ field: SortField; dir: "asc" | "desc" }>({
    field: "name",
    dir: "asc",
  });

  const sortedPlans = useMemo(() => {
    const compare = (a: Plan, b: Plan): number => {
      switch (sort.field) {
        case "speed":
          return compareNumber(a.download_speed_mbps, b.download_speed_mbps);
        case "floor":
          return compareNumber(a.guaranteed_floor_percent, b.guaranteed_floor_percent);
        case "price":
          return compareNumber(Number(a.price), Number(b.price));
        default:
          return compareText(a.name, b.name);
      }
    };
    const sorted = [...plans].sort(compare);
    return sort.dir === "asc" ? sorted : sorted.reverse();
  }, [plans, sort]);

  function toggleSort(field: SortField) {
    setSort((prev) =>
      prev.field === field ? { field, dir: prev.dir === "asc" ? "desc" : "asc" } : { field, dir: "asc" },
    );
  }

  const createMutation = useMutation({
    mutationFn: createPlan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      closeForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: PlanInput }) => updatePlan(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      closeForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlan,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["plans"] }),
  });

  function closeForm() {
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(false);
  }

  function startEdit(plan: Plan) {
    setForm({
      name: plan.name,
      download_speed_mbps: plan.download_speed_mbps,
      upload_speed_mbps: plan.upload_speed_mbps,
      price: plan.price,
      currency: plan.currency,
      guaranteed_floor_percent: plan.guaranteed_floor_percent,
    });
    setEditingId(plan.id);
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
        <h1 className="text-xl font-semibold text-slate-800">Planes</h1>
        <button
          onClick={() => (showForm ? closeForm() : setShowForm(true))}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2"
        >
          {showForm ? "Cancelar" : "Nuevo plan"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <h2 className="col-span-2 text-sm font-medium text-slate-600 -mb-2">
            {editingId ? "Editar plan" : "Nuevo plan"}
          </h2>
          <Field label="Nombre del plan">
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Precio">
            <input
              type="number"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Bajada (Mbps)">
            <input
              type="number"
              value={form.download_speed_mbps}
              onChange={(e) => setForm({ ...form, download_speed_mbps: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Subida (Mbps)">
            <input
              type="number"
              value={form.upload_speed_mbps}
              onChange={(e) => setForm({ ...form, upload_speed_mbps: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field
            label="Piso garantizado (%)"
            hint="% del plan que el cliente mantiene garantizado aunque el enlace esté saturado (QoS). Puede hacer ráfaga hasta el 100% cuando hay banda libre."
          >
            <input
              type="number"
              min={1}
              max={100}
              value={form.guaranteed_floor_percent}
              onChange={(e) => setForm({ ...form, guaranteed_floor_percent: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            {editingId ? "Actualizar plan" : "Guardar plan"}
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <SortableHeader field="name" label="Nombre" sort={sort} onClick={toggleSort} />
              <SortableHeader field="speed" label="Velocidad" sort={sort} onClick={toggleSort} />
              <SortableHeader field="floor" label="Piso QoS" sort={sort} onClick={toggleSort} />
              <SortableHeader field="price" label="Precio" sort={sort} onClick={toggleSort} />
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {sortedPlans.map((plan) => (
              <tr key={plan.id} className="border-t">
                <td className="px-4 py-2">{plan.name}</td>
                <td className="px-4 py-2">
                  {plan.download_speed_mbps}/{plan.upload_speed_mbps} Mbps
                </td>
                <td className="px-4 py-2">{plan.guaranteed_floor_percent}%</td>
                <td className="px-4 py-2">
                  {plan.currency} {Number(plan.price).toFixed(2)}
                </td>
                <td className="px-4 py-2 space-x-2">
                  <button onClick={() => startEdit(plan)} className="text-xs text-blue-600 hover:underline">
                    Editar
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(plan.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
            {plans.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  Aún no hay planes.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
