import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  createDevice,
  deleteDevice,
  listDevices,
  rebootDevice,
  testConnection,
} from "../api/devices";
import type { MikrotikDeviceInput } from "../api/types";

const emptyForm: MikrotikDeviceInput = {
  name: "",
  site: "",
  host: "",
  api_port: 8728,
  api_use_tls: false,
  ssh_port: 22,
  username: "admin",
  password: "",
};

export default function Devices() {
  const queryClient = useQueryClient();
  const { data: devices = [], isLoading } = useQuery({ queryKey: ["devices"], queryFn: listDevices });
  const [form, setForm] = useState<MikrotikDeviceInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [testResult, setTestResult] = useState<Record<string, string>>({});

  const createMutation = useMutation({
    mutationFn: createDevice,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      setForm(emptyForm);
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDevice,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["devices"] }),
  });

  async function handleTest(id: string) {
    setTestResult((prev) => ({ ...prev, [id]: "Probando..." }));
    try {
      const result = await testConnection(id);
      setTestResult((prev) => ({ ...prev, [id]: result.message }));
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    } catch {
      setTestResult((prev) => ({ ...prev, [id]: "Error al probar la conexión." }));
    }
  }

  async function handleReboot(id: string) {
    if (!confirm("¿Reiniciar este equipo Mikrotik ahora?")) return;
    await rebootDevice(id);
    alert("Reinicio enviado.");
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    createMutation.mutate(form);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Equipos Mikrotik</h1>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2"
        >
          {showForm ? "Cancelar" : "Agregar equipo"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-5 grid grid-cols-2 gap-4">
          <input
            required
            placeholder="Nombre"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            placeholder="Sitio / ubicación"
            value={form.site ?? ""}
            onChange={(e) => setForm({ ...form, site: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Host / IP"
            value={form.host}
            onChange={(e) => setForm({ ...form, host: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Usuario"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            type="password"
            placeholder="Contraseña"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            type="number"
            placeholder="Puerto API"
            value={form.api_port}
            onChange={(e) => setForm({ ...form, api_port: Number(e.target.value) })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            type="number"
            placeholder="Puerto SSH"
            value={form.ssh_port}
            onChange={(e) => setForm({ ...form, ssh_port: Number(e.target.value) })}
            className="border rounded px-3 py-2 text-sm"
          />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={form.api_use_tls}
              onChange={(e) => setForm({ ...form, api_use_tls: e.target.checked })}
            />
            Usar TLS en API (puerto 8729)
          </label>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            Guardar equipo
          </button>
        </form>
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500">Cargando...</p>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-4 py-2">Nombre</th>
                <th className="px-4 py-2">Host</th>
                <th className="px-4 py-2">Estado</th>
                <th className="px-4 py-2">RouterOS</th>
                <th className="px-4 py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr key={device.id} className="border-t">
                  <td className="px-4 py-2">
                    <Link to={`/devices/${device.id}`} className="text-slate-800 font-medium hover:underline">
                      {device.name}
                    </Link>
                    {device.site && <div className="text-xs text-slate-400">{device.site}</div>}
                  </td>
                  <td className="px-4 py-2">{device.host}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                        device.status === "online"
                          ? "bg-green-100 text-green-700"
                          : device.status === "offline"
                            ? "bg-red-100 text-red-700"
                            : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {device.status}
                    </span>
                  </td>
                  <td className="px-4 py-2">{device.routeros_version ?? "—"}</td>
                  <td className="px-4 py-2 space-x-2">
                    <button onClick={() => handleTest(device.id)} className="text-xs text-blue-600 hover:underline">
                      Probar conexión
                    </button>
                    <button onClick={() => handleReboot(device.id)} className="text-xs text-amber-600 hover:underline">
                      Reiniciar
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(device.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Eliminar
                    </button>
                    {testResult[device.id] && (
                      <div className="text-xs text-slate-400 mt-1">{testResult[device.id]}</div>
                    )}
                  </td>
                </tr>
              ))}
              {devices.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    Aún no hay equipos registrados.
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
