import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  applyQosPlanBootstrap,
  previewQosPlanBootstrap,
  removeQosPlanBootstrap,
} from "../api/qos";
import { listInterfaces } from "../api/interfaces";
import { listMangleRules } from "../api/wanBalancing";
import { listPlans } from "../api/plans";
import type { QosPlanBootstrapInput, QosPlanBootstrapResponse, WanCommandResult } from "../api/types";

const emptyInput: QosPlanBootstrapInput = {
  lan_interface: "",
  wan_interface: "",
  priority_tcp_ports: [],
  priority_udp_ports: [],
  realtime_tcp_max_size: 128,
  realtime_udp_max_size: 200,
};

export default function QosPlans({ deviceId }: { deviceId: string }) {
  const { data: ifaces = [] } = useQuery({
    queryKey: ["interfaces", deviceId],
    queryFn: () => listInterfaces(deviceId),
    retry: false,
  });
  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: listPlans });
  const { data: mangleRules = [], refetch: refetchMangle } = useQuery({
    queryKey: ["mangle-rules", deviceId],
    queryFn: () => listMangleRules(deviceId),
    retry: false,
  });

  const [planId, setPlanId] = useState("");
  const [input, setInput] = useState<QosPlanBootstrapInput>(emptyInput);
  const [priorityTcpText, setPriorityTcpText] = useState("");
  const [priorityUdpText, setPriorityUdpText] = useState("");

  const [previewCommands, setPreviewCommands] = useState<WanCommandResult[] | null>(null);
  const [previewedFor, setPreviewedFor] = useState<string | null>(null);
  const [applyResult, setApplyResult] = useState<QosPlanBootstrapResponse | null>(null);
  const [loading, setLoading] = useState<"preview" | "apply" | "remove" | null>(null);
  const [error, setError] = useState<string | null>(null);

  function currentPayload(): QosPlanBootstrapInput {
    return {
      ...input,
      priority_tcp_ports: parsePorts(priorityTcpText),
      priority_udp_ports: parsePorts(priorityUdpText),
    };
  }

  const formSignature = `${planId}:${JSON.stringify(currentPayload())}`;
  const canApply = previewCommands !== null && previewedFor === formSignature && planId !== "";

  function updateInput(patch: Partial<QosPlanBootstrapInput>) {
    setInput((prev) => ({ ...prev, ...patch }));
    setPreviewCommands(null);
    setApplyResult(null);
  }

  async function handlePreview() {
    if (!planId) return;
    setError(null);
    setApplyResult(null);
    setLoading("preview");
    try {
      const result = await previewQosPlanBootstrap(deviceId, planId, currentPayload());
      setPreviewCommands(result.commands);
      setPreviewedFor(formSignature);
    } catch (err) {
      setError(axiosErrorMessage(err) ?? "No se pudo generar la vista previa.");
      setPreviewCommands(null);
    } finally {
      setLoading(null);
    }
  }

  async function handleApply() {
    if (!canApply) return;
    const plan = plans.find((p) => p.id === planId);
    const confirmed = confirm(
      `Esto crea la infraestructura QoS del plan "${plan?.name ?? planId}" en este equipo ` +
        "(address-list, PCQ, mangle, queue tree) — se hace UNA VEZ por plan, no por cliente. " +
        "¿Aplicar de todas formas?",
    );
    if (!confirmed) return;

    setError(null);
    setLoading("apply");
    try {
      const result = await applyQosPlanBootstrap(deviceId, planId, currentPayload());
      setApplyResult(result);
      setPreviewCommands(result.commands);
      refetchMangle();
    } catch (err) {
      setError(axiosErrorMessage(err) ?? "No se pudo aplicar la configuración.");
    } finally {
      setLoading(null);
    }
  }

  async function handleRemove() {
    if (!planId) return;
    const plan = plans.find((p) => p.id === planId);
    const confirmed = confirm(
      `Esto borra toda la infraestructura QoS del plan "${plan?.name ?? planId}" en este equipo ` +
        "(mangle, queue tree, PCQ, address-list) — los clientes de este plan dejan de tener shaping. " +
        "¿Desmontar de todas formas?",
    );
    if (!confirmed) return;

    setError(null);
    setLoading("remove");
    try {
      await removeQosPlanBootstrap(deviceId, planId);
      setPreviewCommands(null);
      setApplyResult(null);
      refetchMangle();
    } catch (err) {
      setError(axiosErrorMessage(err) ?? "No se pudo desmontar la configuración.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-slate-800">QoS por plan (shaping)</h2>
      <p className="text-xs text-slate-500">
        3 niveles de prioridad por paquete (sin DPI: tamaño de paquete + puertos interactivos =
        tiempo real; puertos configurados = prioridad; resto = bulk), piso garantizado + techo de
        ráfaga por plan, PCQ para repartir justo entre los clientes activos. Se aplica UNA VEZ por
        plan por equipo — dar de alta/baja un cliente después es una sola llamada, no toca esto.
        Verificado contra un CCR2004 real antes de escribirse — ver docs/qos-design si existe, o el
        módulo services/mikrotik/qos.py del backend.
      </p>

      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-xs font-medium text-slate-500 mb-2">
          Reglas de mangle actuales en el equipo ({mangleRules.length})
        </h3>
        <div className="text-xs text-slate-600 max-h-32 overflow-y-auto space-y-1">
          {mangleRules.length === 0 && <p className="text-slate-400">Sin reglas.</p>}
          {mangleRules.slice(0, 20).map((row, i) => (
            <div key={i} className="truncate" title={JSON.stringify(row)}>
              {String(row["comment"] ?? row["action"] ?? row["chain"] ?? JSON.stringify(row))}
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-5 space-y-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Plan</label>
          <select
            value={planId}
            onChange={(e) => {
              setPlanId(e.target.value);
              setPreviewCommands(null);
              setApplyResult(null);
            }}
            className="border rounded px-3 py-2 text-sm w-full max-w-sm bg-white"
          >
            <option value="">Selecciona un plan...</option>
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name} ({plan.download_speed_mbps}/{plan.upload_speed_mbps} Mbps, piso{" "}
                {plan.guaranteed_floor_percent}%)
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Interfaz LAN/bridge (por donde sale el tráfico hacia los clientes — descarga)
            </label>
            <select
              value={input.lan_interface}
              onChange={(e) => updateInput({ lan_interface: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="">Selecciona una interfaz...</option>
              {ifaces.map((iface) => (
                <option key={iface.id} value={iface.name}>
                  {iface.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Interfaz WAN (por donde sale hacia internet — subida)
            </label>
            <select
              value={input.wan_interface}
              onChange={(e) => updateInput({ wan_interface: e.target.value })}
              className="border rounded px-3 py-2 text-sm w-full bg-white"
            >
              <option value="">Selecciona una interfaz...</option>
              {ifaces.map((iface) => (
                <option key={iface.id} value={iface.name}>
                  {iface.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Puertos TCP de prioridad (opcional, separados por coma — ej. 8100,32400)
            </label>
            <input
              value={priorityTcpText}
              onChange={(e) => {
                setPriorityTcpText(e.target.value);
                setPreviewCommands(null);
              }}
              placeholder="Vacío = usa los defaults del backend"
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Puertos UDP de prioridad (opcional, separados por coma)
            </label>
            <input
              value={priorityUdpText}
              onChange={(e) => {
                setPriorityUdpText(e.target.value);
                setPreviewCommands(null);
              }}
              placeholder="Vacío = usa los defaults del backend"
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Tamaño máx. de paquete TCP considerado "tiempo real" (bytes)
            </label>
            <input
              type="number"
              value={input.realtime_tcp_max_size}
              onChange={(e) => updateInput({ realtime_tcp_max_size: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Tamaño máx. de paquete UDP considerado "tiempo real" (bytes)
            </label>
            <input
              type="number"
              value={input.realtime_udp_max_size}
              onChange={(e) => updateInput({ realtime_udp_max_size: Number(e.target.value) })}
              className="border rounded px-3 py-2 text-sm w-full"
            />
          </div>
        </div>

        <div className="flex gap-2 pt-2 border-t">
          <button
            onClick={handlePreview}
            disabled={loading !== null || !planId || !input.lan_interface || !input.wan_interface}
            className="bg-slate-700 text-white text-sm rounded px-4 py-2 disabled:opacity-50"
          >
            {loading === "preview" ? "Generando..." : "Vista previa"}
          </button>
          <button
            onClick={handleApply}
            disabled={!canApply || loading !== null}
            className="bg-red-700 text-white text-sm rounded px-4 py-2 disabled:opacity-50"
            title={!canApply ? "Primero genera una vista previa con estos mismos datos" : undefined}
          >
            {loading === "apply" ? "Aplicando..." : "Aplicar (crear infraestructura del plan)"}
          </button>
          <button
            onClick={handleRemove}
            disabled={!planId || loading !== null}
            className="text-red-600 text-sm rounded px-4 py-2 border border-red-300 disabled:opacity-50 ml-auto"
          >
            {loading === "remove" ? "Desmontando..." : "Desmontar plan de este equipo"}
          </button>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>

      {previewCommands && (
        <div className="bg-slate-900 rounded-lg shadow p-5 overflow-x-auto">
          <h3 className="text-sm font-medium text-slate-300 mb-3">
            {applyResult ? "Resultado de aplicar" : "Vista previa"} ({previewCommands.length} comandos)
          </h3>
          <div className="space-y-1 font-mono text-xs">
            {previewCommands.map((cmd, i) => (
              <div key={i} className="text-slate-200">
                <span className="text-slate-500"># {cmd.description}</span>
                <br />
                {applyResult && (
                  <span className={cmd.executed ? "text-green-400" : "text-red-400"}>
                    {cmd.executed ? "✓ " : "✗ "}
                  </span>
                )}
                {cmd.path} {Object.entries(cmd.params).map(([k, v]) => `${k}="${v}"`).join(" ")}
                {cmd.error && <span className="text-red-400"> — {cmd.error}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function parsePorts(text: string): number[] {
  return text
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean)
    .map(Number)
    .filter((n) => Number.isFinite(n) && n > 0);
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
