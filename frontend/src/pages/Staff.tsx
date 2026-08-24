import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createUser, listUsers, updateUser } from "../api/users";
import { listZones } from "../api/zones";
import type { UserInput, UserRead, UserRole } from "../api/types";
import Field from "../components/Field";

const emptyForm: UserInput = {
  full_name: "",
  email: "",
  password: "",
  role: "technician",
  zone_ids: [],
};

const roleLabels: Record<UserRole, string> = {
  admin: "Administrador",
  technician: "Técnico",
  finance: "Finanzas",
};

export default function Staff() {
  const queryClient = useQueryClient();
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const { data: zones = [] } = useQuery({ queryKey: ["zones"], queryFn: listZones });
  const [form, setForm] = useState<UserInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      closeForm();
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo crear el usuario."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<UserInput> }) => updateUser(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      closeForm();
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo actualizar el usuario."),
  });

  function closeForm() {
    setForm(emptyForm);
    setEditingId(null);
    setShowForm(false);
  }

  function startEdit(user: UserRead) {
    setForm({
      full_name: user.full_name,
      email: user.email,
      password: "",
      role: user.role,
      is_active: user.is_active,
      zone_ids: user.zones.map((z) => z.id),
    });
    setEditingId(user.id);
    setShowForm(true);
  }

  function toggleZone(zoneId: string) {
    setForm((prev) => ({
      ...prev,
      zone_ids: prev.zone_ids.includes(zoneId)
        ? prev.zone_ids.filter((id) => id !== zoneId)
        : [...prev.zone_ids, zoneId],
    }));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (editingId) {
      // Sin contraseña vacía: no se toca si el admin la dejó en blanco al editar.
      const { password, ...rest } = form;
      const payload = password ? form : rest;
      updateMutation.mutate({ id: editingId, payload });
    } else {
      createMutation.mutate(form);
    }
  }

  function toggleActive(user: UserRead) {
    updateMutation.mutate({ id: user.id, payload: { is_active: !user.is_active } });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Personal</h1>
        <button
          onClick={() => (showForm ? closeForm() : setShowForm(true))}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2"
        >
          {showForm ? "Cancelar" : "Nuevo usuario"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <h2 className="col-span-2 text-sm font-medium text-slate-600 -mb-2">
            {editingId ? "Editar usuario" : "Nuevo usuario"}
          </h2>
          <Field label="Nombre completo">
            <input
              required
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Correo">
            <input
              required
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label={editingId ? "Nueva contraseña (dejar vacío para no cambiarla)" : "Contraseña"}>
            <input
              required={!editingId}
              type="password"
              value={form.password ?? ""}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </Field>
          <Field label="Rol">
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="admin">Administrador</option>
              <option value="technician">Técnico</option>
              <option value="finance">Finanzas</option>
            </select>
          </Field>
          <Field
            label="Zonas asignadas"
            hint="Un administrador siempre tiene acceso total, sin importar las zonas. Técnico/Finanzas sin ninguna zona marcada no ve ningún cliente ni equipo."
          >
            <div className="flex flex-wrap gap-3 border rounded px-3 py-2">
              {zones.map((zone) => (
                <label key={zone.id} className="flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={form.zone_ids.includes(zone.id)}
                    onChange={() => toggleZone(zone.id)}
                  />
                  {zone.name}
                </label>
              ))}
              {zones.length === 0 && <span className="text-xs text-slate-400">Aún no hay zonas creadas.</span>}
            </div>
          </Field>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            {editingId ? "Actualizar usuario" : "Guardar usuario"}
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Nombre</th>
              <th className="px-4 py-2">Correo</th>
              <th className="px-4 py-2">Rol</th>
              <th className="px-4 py-2">Zonas</th>
              <th className="px-4 py-2">Estado</th>
              <th className="px-4 py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-t">
                <td className="px-4 py-2">{user.full_name}</td>
                <td className="px-4 py-2">{user.email}</td>
                <td className="px-4 py-2">{roleLabels[user.role]}</td>
                <td className="px-4 py-2 text-xs text-slate-500">
                  {user.role === "admin" ? "Todas" : user.zones.map((z) => z.name).join(", ") || "Ninguna"}
                </td>
                <td className="px-4 py-2">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                      user.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {user.is_active ? "Activo" : "Inactivo"}
                  </span>
                </td>
                <td className="px-4 py-2 space-x-2">
                  <button onClick={() => startEdit(user)} className="text-xs text-blue-600 hover:underline">
                    Editar
                  </button>
                  <button onClick={() => toggleActive(user)} className="text-xs text-amber-600 hover:underline">
                    {user.is_active ? "Desactivar" : "Activar"}
                  </button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Aún no hay usuarios.
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
