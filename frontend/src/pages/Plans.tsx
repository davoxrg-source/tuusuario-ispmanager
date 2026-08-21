import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createPlan, deletePlan, listPlans, type PlanInput } from "../api/plans";

const emptyForm: PlanInput = {
  name: "",
  download_speed_mbps: 10,
  upload_speed_mbps: 5,
  price: 0,
  currency: "USD",
};

export default function Plans() {
  const queryClient = useQueryClient();
  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: listPlans });
  const [form, setForm] = useState<PlanInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);

  const createMutation = useMutation({
    mutationFn: createPlan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      setForm(emptyForm);
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlan,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["plans"] }),
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate(form);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Planes</h1>
        <button onClick={() => setShowForm((s) => !s)} className="bg-slate-900 text-white text-sm rounded px-4 py-2">
          {showForm ? "Cancelar" : "Nuevo plan"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <input
            required
            placeholder="Nombre del plan"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            type="number"
            placeholder="Precio"
            value={form.price}
            onChange={(e) => setForm({ ...form, price: Number(e.target.value) })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            type="number"
            placeholder="Bajada (Mbps)"
            value={form.download_speed_mbps}
            onChange={(e) => setForm({ ...form, download_speed_mbps: Number(e.target.value) })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            type="number"
            placeholder="Subida (Mbps)"
            value={form.upload_speed_mbps}
            onChange={(e) => setForm({ ...form, upload_speed_mbps: Number(e.target.value) })}
            className="border rounded px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            Guardar plan
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Nombre</th>
              <th className="px-4 py-2">Velocidad</th>
              <th className="px-4 py-2">Precio</th>
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {plans.map((plan) => (
              <tr key={plan.id} className="border-t">
                <td className="px-4 py-2">{plan.name}</td>
                <td className="px-4 py-2">
                  {plan.download_speed_mbps}/{plan.upload_speed_mbps} Mbps
                </td>
                <td className="px-4 py-2">
                  {plan.currency} {Number(plan.price).toFixed(2)}
                </td>
                <td className="px-4 py-2">
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
                <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
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
