import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addBridgePort,
  addIpAddress,
  createBridge,
  listBridgePorts,
  listBridges,
  listInterfaces,
  listIpAddresses,
  removeBridge,
  removeIpAddress,
  setupPppoeServer,
} from "../api/interfaces";
import type { PppoeServerSetupInput } from "../api/types";

const emptyPppoeForm: PppoeServerSetupInput = {
  interface: "",
  service_name: "isp-pppoe",
  pool_start: "",
  pool_end: "",
  profile_name: "",
  local_address: "",
};

export default function InterfaceConfig({ deviceId }: { deviceId: string }) {
  const queryClient = useQueryClient();

  const { data: ifaces = [], isLoading: loadingIfaces } = useQuery({
    queryKey: ["interfaces", deviceId],
    queryFn: () => listInterfaces(deviceId),
    retry: false,
  });
  const { data: ipAddresses = [] } = useQuery({
    queryKey: ["ip-addresses", deviceId],
    queryFn: () => listIpAddresses(deviceId),
    retry: false,
  });
  const { data: bridges = [] } = useQuery({
    queryKey: ["bridges", deviceId],
    queryFn: () => listBridges(deviceId),
    retry: false,
  });
  const { data: bridgePorts = [] } = useQuery({
    queryKey: ["bridge-ports", deviceId],
    queryFn: () => listBridgePorts(deviceId),
    retry: false,
  });

  const [ipForm, setIpForm] = useState({ interface: "", address: "" });
  const [bridgeName, setBridgeName] = useState("");
  const [portForm, setPortForm] = useState({ bridge: "", interface: "" });
  const [pppoeForm, setPppoeForm] = useState<PppoeServerSetupInput>(emptyPppoeForm);
  const [pppoeResult, setPppoeResult] = useState<string | null>(null);

  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ["interfaces", deviceId] });
    queryClient.invalidateQueries({ queryKey: ["ip-addresses", deviceId] });
    queryClient.invalidateQueries({ queryKey: ["bridges", deviceId] });
    queryClient.invalidateQueries({ queryKey: ["bridge-ports", deviceId] });
  }

  const addIpMutation = useMutation({
    mutationFn: () => addIpAddress(deviceId, ipForm),
    onSuccess: () => {
      setIpForm({ interface: "", address: "" });
      invalidateAll();
    },
  });

  const removeIpMutation = useMutation({
    mutationFn: (ipId: string) => removeIpAddress(deviceId, ipId),
    onSuccess: invalidateAll,
  });

  const createBridgeMutation = useMutation({
    mutationFn: () => createBridge(deviceId, bridgeName),
    onSuccess: () => {
      setBridgeName("");
      invalidateAll();
    },
  });

  const removeBridgeMutation = useMutation({
    mutationFn: (bridgeId: string) => removeBridge(deviceId, bridgeId),
    onSuccess: invalidateAll,
  });

  const addPortMutation = useMutation({
    mutationFn: () => addBridgePort(deviceId, portForm.bridge, portForm.interface),
    onSuccess: () => {
      setPortForm({ bridge: "", interface: "" });
      invalidateAll();
    },
  });

  async function handlePppoeSubmit(e: FormEvent) {
    e.preventDefault();
    setPppoeResult(null);
    try {
      await setupPppoeServer(deviceId, pppoeForm);
      setPppoeResult("Servidor PPPoE configurado correctamente.");
      setPppoeForm(emptyPppoeForm);
      invalidateAll();
    } catch {
      setPppoeResult("No se pudo configurar el servidor PPPoE. Revisa los datos e intenta de nuevo.");
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-slate-800">Configuración de interfaces</h2>

      {/* Interfaces */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <h3 className="text-sm font-medium text-slate-600 px-5 pt-4 pb-2">Interfaces</h3>
        {loadingIfaces ? (
          <p className="px-5 pb-4 text-sm text-slate-400">Cargando...</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-4 py-2">Nombre</th>
                <th className="px-4 py-2">Tipo</th>
                <th className="px-4 py-2">MAC</th>
                <th className="px-4 py-2">MTU</th>
                <th className="px-4 py-2">Estado</th>
              </tr>
            </thead>
            <tbody>
              {ifaces.map((iface) => (
                <tr key={iface.id} className="border-t">
                  <td className="px-4 py-2">{iface.name}</td>
                  <td className="px-4 py-2">{iface.type}</td>
                  <td className="px-4 py-2 font-mono text-xs">{iface.mac_address ?? "—"}</td>
                  <td className="px-4 py-2">{iface.mtu ?? "—"}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                        iface.disabled
                          ? "bg-slate-100 text-slate-500"
                          : iface.running
                            ? "bg-green-100 text-green-700"
                            : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {iface.disabled ? "deshabilitada" : iface.running ? "activa" : "sin enlace"}
                    </span>
                  </td>
                </tr>
              ))}
              {ifaces.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    Sin datos (equipo no accesible ahora mismo).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Direcciones IP */}
      <div className="bg-white rounded-lg shadow p-5 space-y-3">
        <h3 className="text-sm font-medium text-slate-600">Direcciones IP</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Dirección</th>
              <th className="py-1">Red</th>
              <th className="py-1">Interfaz</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody>
            {ipAddresses.map((ip) => (
              <tr key={ip.id} className="border-t">
                <td className="py-1">{ip.address}</td>
                <td className="py-1">{ip.network ?? "—"}</td>
                <td className="py-1">{ip.interface}</td>
                <td className="py-1">
                  <button
                    onClick={() => removeIpMutation.mutate(ip.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
            {ipAddresses.length === 0 && (
              <tr>
                <td colSpan={4} className="py-4 text-center text-slate-400">
                  Sin direcciones IP configuradas.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            addIpMutation.mutate();
          }}
          className="flex gap-2 pt-2 border-t"
        >
          <input
            required
            placeholder="Interfaz (ej. ether1)"
            value={ipForm.interface}
            onChange={(e) => setIpForm({ ...ipForm, interface: e.target.value })}
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <input
            required
            placeholder="IP/CIDR (ej. 192.168.1.1/24)"
            value={ipForm.address}
            onChange={(e) => setIpForm({ ...ipForm, address: e.target.value })}
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <button
            type="submit"
            disabled={addIpMutation.isPending}
            className="bg-slate-900 text-white text-sm rounded px-4 py-2 disabled:opacity-50"
          >
            Agregar IP
          </button>
        </form>
      </div>

      {/* Bridges */}
      <div className="bg-white rounded-lg shadow p-5 space-y-3">
        <h3 className="text-sm font-medium text-slate-600">Bridges</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Nombre</th>
              <th className="py-1">Puertos</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody>
            {bridges.map((bridge) => (
              <tr key={bridge.id} className="border-t align-top">
                <td className="py-1">{bridge.name}</td>
                <td className="py-1">
                  {bridgePorts
                    .filter((p) => p.bridge === bridge.name)
                    .map((p) => p.interface)
                    .join(", ") || "—"}
                </td>
                <td className="py-1">
                  <button
                    onClick={() => removeBridgeMutation.mutate(bridge.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Eliminar
                  </button>
                </td>
              </tr>
            ))}
            {bridges.length === 0 && (
              <tr>
                <td colSpan={3} className="py-4 text-center text-slate-400">
                  Sin bridges configurados.
                </td>
              </tr>
            )}
          </tbody>
        </table>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            createBridgeMutation.mutate();
          }}
          className="flex gap-2 pt-2 border-t"
        >
          <input
            required
            placeholder="Nombre del bridge (ej. bridge-lan)"
            value={bridgeName}
            onChange={(e) => setBridgeName(e.target.value)}
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <button
            type="submit"
            disabled={createBridgeMutation.isPending}
            className="bg-slate-900 text-white text-sm rounded px-4 py-2 disabled:opacity-50"
          >
            Crear bridge
          </button>
        </form>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            addPortMutation.mutate();
          }}
          className="flex gap-2"
        >
          <input
            required
            placeholder="Bridge existente"
            value={portForm.bridge}
            onChange={(e) => setPortForm({ ...portForm, bridge: e.target.value })}
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <input
            required
            placeholder="Interfaz a agregar (ej. ether2)"
            value={portForm.interface}
            onChange={(e) => setPortForm({ ...portForm, interface: e.target.value })}
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <button
            type="submit"
            disabled={addPortMutation.isPending}
            className="bg-slate-900 text-white text-sm rounded px-4 py-2 disabled:opacity-50"
          >
            Agregar puerto
          </button>
        </form>
      </div>

      {/* PPPoE server */}
      <div className="bg-white rounded-lg shadow p-5 space-y-3">
        <h3 className="text-sm font-medium text-slate-600">Configurar servidor PPPoE</h3>
        <p className="text-xs text-slate-400">
          Crea de una vez el pool de IPs, el perfil PPP y el servidor PPPoE en la interfaz elegida.
        </p>
        <form onSubmit={handlePppoeSubmit} className="grid grid-cols-2 gap-3">
          <input
            required
            placeholder="Interfaz (ej. ether1 o bridge-lan)"
            value={pppoeForm.interface}
            onChange={(e) => setPppoeForm({ ...pppoeForm, interface: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Nombre del servicio"
            value={pppoeForm.service_name}
            onChange={(e) => setPppoeForm({ ...pppoeForm, service_name: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Nombre del perfil (ej. clientes)"
            value={pppoeForm.profile_name}
            onChange={(e) => setPppoeForm({ ...pppoeForm, profile_name: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="IP local del servidor (ej. 10.10.10.1)"
            value={pppoeForm.local_address}
            onChange={(e) => setPppoeForm({ ...pppoeForm, local_address: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Pool desde (ej. 10.10.10.2)"
            value={pppoeForm.pool_start}
            onChange={(e) => setPppoeForm({ ...pppoeForm, pool_start: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <input
            required
            placeholder="Pool hasta (ej. 10.10.10.254)"
            value={pppoeForm.pool_end}
            onChange={(e) => setPppoeForm({ ...pppoeForm, pool_end: e.target.value })}
            className="border rounded px-3 py-2 text-sm"
          />
          <button
            type="submit"
            className="col-span-2 bg-slate-900 text-white text-sm rounded py-2"
          >
            Configurar servidor PPPoE
          </button>
        </form>
        {pppoeResult && <p className="text-xs text-slate-500">{pppoeResult}</p>}
      </div>
    </div>
  );
}
