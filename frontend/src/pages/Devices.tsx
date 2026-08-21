import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  createDevice,
  deleteDevice,
  listDevices,
  listDiscoveredDevices,
  rebootDevice,
  resetDeviceToDefaults,
  testConnection,
} from "../api/devices";
import type { DiscoveredDevice, MikrotikDeviceInput } from "../api/types";

const emptyForm: MikrotikDeviceInput = {
  name: "",
  site: "",
  host: "",
  mac_address: "",
  api_port: 8728,
  api_use_tls: false,
  ssh_port: 22,
  username: "admin",
  password: "",
};

export default function Devices() {
  const queryClient = useQueryClient();
  const { data: devices = [], isLoading } = useQuery({ queryKey: ["devices"], queryFn: listDevices });
  const { data: discovered = [] } = useQuery({
    queryKey: ["devices-discovered"],
    queryFn: listDiscoveredDevices,
    refetchInterval: 15000,
    retry: false,
  });
  const [form, setForm] = useState<MikrotikDeviceInput>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [testResult, setTestResult] = useState<Record<string, string>>({});

  const knownMacs = new Set(devices.map((d) => d.mac_address).filter(Boolean));
  const undiscoveredDevices = discovered.filter((d) => !knownMacs.has(d.mac_address));

  function handleRegisterDiscovered(d: DiscoveredDevice) {
    setForm({
      ...emptyForm,
      name: d.identity || d.ip_address,
      host: d.ip_address,
      mac_address: d.mac_address,
    });
    setShowForm(true);
  }

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
      const message = result.resolved_via_mac
        ? `${result.message} (IP actualizada automáticamente a ${result.updated_host ?? "—"} por MAC)`
        : result.message;
      setTestResult((prev) => ({ ...prev, [id]: message }));
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

  async function handleResetToDefaults(id: string, name: string) {
    const typed = prompt(
      `Esto BORRA TODA la configuración de "${name}" y lo reinicia — quedará sin ninguna IP asignada ` +
        `(solo se podrá encontrar por MAC).\n\nEsta acción no se puede deshacer.\n\n` +
        `Para confirmar, escribe exactamente el nombre del equipo: ${name}`,
    );
    if (typed !== name) {
      if (typed !== null) alert("El nombre no coincide. No se hizo ningún cambio.");
      return;
    }
    try {
      const result = await resetDeviceToDefaults(id, name);
      alert(result.detail);
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    } catch {
      alert("No se pudo restablecer el equipo a su configuración de fábrica.");
    }
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

      {undiscoveredDevices.length > 0 && (
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-sm font-medium text-slate-600 mb-1">Detectados en la red</h2>
          <p className="text-xs text-slate-400 mb-3">
            Equipos Mikrotik anunciándose por MNDP en esta red que aún no están registrados.
            Requiere que este servidor esté en el mismo segmento de red que el equipo.
          </p>
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">Identidad</th>
                <th className="py-1">IP</th>
                <th className="py-1">MAC</th>
                <th className="py-1">Visto hace</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {undiscoveredDevices.map((d) => (
                <tr key={d.mac_address} className="border-t">
                  <td className="py-1">{d.identity ?? "—"}</td>
                  <td className="py-1">{d.ip_address}</td>
                  <td className="py-1 font-mono text-xs">{d.mac_address}</td>
                  <td className="py-1">{Math.round(d.seen_seconds_ago)}s</td>
                  <td className="py-1">
                    <button
                      onClick={() => handleRegisterDiscovered(d)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Registrar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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
            placeholder="MAC (opcional, para redescubrir si cambia la IP)"
            value={form.mac_address ?? ""}
            onChange={(e) => setForm({ ...form, mac_address: e.target.value })}
            className="border rounded px-3 py-2 text-sm font-mono"
          />
          <input
            required
            placeholder="Usuario"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <div>
            <input
              type="password"
              placeholder="Contraseña"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
            <p className="text-xs text-slate-400 mt-1">
              Déjala vacía si el equipo es nuevo de fábrica y aún no tiene contraseña configurada.
            </p>
          </div>
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
                <th className="px-4 py-2">MAC</th>
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
                  <td className="px-4 py-2 font-mono text-xs">{device.mac_address ?? "—"}</td>
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
                      onClick={() => handleResetToDefaults(device.id, device.name)}
                      className="text-xs text-red-700 hover:underline font-medium"
                      title="Borra TODA la configuración del equipo y lo reinicia sin config de fábrica"
                    >
                      Restablecer a fábrica
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
                  <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
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
