import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyWanBalancing,
  listMangleRules,
  listNatRules,
  listRoutes,
  previewWanBalancing,
} from "../api/wanBalancing";
import type {
  PublicBlockPin,
  WanBalancingInput,
  WanBalancingResponse,
  WanCommandResult,
  WanLinkInput,
} from "../api/types";

const emptyWan: WanLinkInput = { interface: "", gateway: "", distance: 1 };
const emptyBlock: PublicBlockPin = { cidr: "", wan_interface: "" };

export default function WanBalancing({ deviceId }: { deviceId: string }) {
  const queryClient = useQueryClient();

  const { data: routes = [] } = useQuery({
    queryKey: ["routes", deviceId],
    queryFn: () => listRoutes(deviceId),
    retry: false,
  });
  const { data: mangleRules = [] } = useQuery({
    queryKey: ["mangle-rules", deviceId],
    queryFn: () => listMangleRules(deviceId),
    retry: false,
  });
  const { data: natRules = [] } = useQuery({
    queryKey: ["nat-rules", deviceId],
    queryFn: () => listNatRules(deviceId),
    retry: false,
  });

  const [lanInterface, setLanInterface] = useState("");
  const [wans, setWans] = useState<WanLinkInput[]>([{ ...emptyWan }, { ...emptyWan }]);
  const [publicBlocks, setPublicBlocks] = useState<PublicBlockPin[]>([]);

  const [previewCommands, setPreviewCommands] = useState<WanCommandResult[] | null>(null);
  const [previewedFor, setPreviewedFor] = useState<string | null>(null);
  const [applyResult, setApplyResult] = useState<WanBalancingResponse | null>(null);
  const [loading, setLoading] = useState<"preview" | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);

  function currentPayload(): WanBalancingInput {
    return { lan_interface: lanInterface, wans, public_blocks: publicBlocks };
  }

  const formSignature = JSON.stringify(currentPayload());
  const canApply = previewCommands !== null && previewedFor === formSignature;

  function updateWan(index: number, patch: Partial<WanLinkInput>) {
    setWans((prev) => prev.map((w, i) => (i === index ? { ...w, ...patch } : w)));
    setPreviewCommands(null);
  }

  function updateBlock(index: number, patch: Partial<PublicBlockPin>) {
    setPublicBlocks((prev) => prev.map((b, i) => (i === index ? { ...b, ...patch } : b)));
    setPreviewCommands(null);
  }

  async function handlePreview() {
    setError(null);
    setApplyResult(null);
    setLoading("preview");
    try {
      const result = await previewWanBalancing(deviceId, currentPayload());
      setPreviewCommands(result.commands);
      setPreviewedFor(formSignature);
    } catch (err) {
      const message = axiosErrorMessage(err) ?? "No se pudo generar la vista previa.";
      setError(message);
      setPreviewCommands(null);
    } finally {
      setLoading(null);
    }
  }

  async function handleApply() {
    if (!canApply) return;
    const confirmed = confirm(
      "Esto va a modificar el ruteo real del equipo (tablas de ruteo, mangle, NAT). " +
        "Un error aquí puede dejar sin internet a todo el equipo. ¿Aplicar de todas formas?",
    );
    if (!confirmed) return;

    setError(null);
    setLoading("apply");
    try {
      const result = await applyWanBalancing(deviceId, currentPayload());
      setApplyResult(result);
      setPreviewCommands(result.commands);
      queryClient.invalidateQueries({ queryKey: ["routes", deviceId] });
      queryClient.invalidateQueries({ queryKey: ["mangle-rules", deviceId] });
      queryClient.invalidateQueries({ queryKey: ["nat-rules", deviceId] });
    } catch (err) {
      const message = axiosErrorMessage(err) ?? "No se pudo aplicar la configuración.";
      setError(message);
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-slate-800">Balanceo y failover multi-WAN</h2>
      <p className="text-xs text-slate-500">
        Balanceo PCC para tráfico NATeado entre 2+ WAN, con bloques de IP pública (Proxy ARP) fijos a
        su propia WAN. Esto modifica el ruteo real del equipo — siempre revisa la vista previa antes
        de aplicar.
      </p>

      {/* Estado actual */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StateCard title="Rutas" rows={routes} />
        <StateCard title="Reglas de mangle" rows={mangleRules} />
        <StateCard title="NAT" rows={natRules} />
      </div>

      {/* Formulario */}
      <div className="bg-white rounded-lg shadow p-5 space-y-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">
            Interfaz/bridge LAN (donde llegan los clientes NATeados)
          </label>
          <input
            placeholder="ej. bridge-lan"
            value={lanInterface}
            onChange={(e) => {
              setLanInterface(e.target.value);
              setPreviewCommands(null);
            }}
            className="border rounded px-3 py-2 text-sm w-full max-w-sm"
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-slate-500">WAN (2 o más)</label>
            <button
              onClick={() => {
                setWans((prev) => [...prev, { ...emptyWan }]);
                setPreviewCommands(null);
              }}
              className="text-xs text-blue-600 hover:underline"
            >
              + agregar WAN
            </button>
          </div>
          <div className="space-y-2">
            {wans.map((wan, i) => (
              <div key={i} className="flex gap-2">
                <input
                  placeholder="Interfaz (ej. ether1)"
                  value={wan.interface}
                  onChange={(e) => updateWan(i, { interface: e.target.value })}
                  className="border rounded px-3 py-2 text-sm flex-1"
                />
                <input
                  placeholder="Gateway"
                  value={wan.gateway}
                  onChange={(e) => updateWan(i, { gateway: e.target.value })}
                  className="border rounded px-3 py-2 text-sm flex-1"
                />
                <input
                  type="number"
                  placeholder="Distancia"
                  value={wan.distance}
                  onChange={(e) => updateWan(i, { distance: Number(e.target.value) })}
                  className="border rounded px-3 py-2 text-sm w-28"
                />
                {wans.length > 2 && (
                  <button
                    onClick={() => {
                      setWans((prev) => prev.filter((_, idx) => idx !== i));
                      setPreviewCommands(null);
                    }}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Quitar
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-slate-500">
              Bloques de IP pública fijos a una WAN (Proxy ARP, opcional)
            </label>
            <button
              onClick={() => {
                setPublicBlocks((prev) => [...prev, { ...emptyBlock }]);
                setPreviewCommands(null);
              }}
              className="text-xs text-blue-600 hover:underline"
            >
              + agregar bloque
            </button>
          </div>
          <div className="space-y-2">
            {publicBlocks.map((block, i) => (
              <div key={i} className="flex gap-2">
                <input
                  placeholder="CIDR (ej. 203.0.113.0/28)"
                  value={block.cidr}
                  onChange={(e) => updateBlock(i, { cidr: e.target.value })}
                  className="border rounded px-3 py-2 text-sm flex-1"
                />
                <input
                  placeholder="Interfaz WAN a la que va fijo"
                  value={block.wan_interface}
                  onChange={(e) => updateBlock(i, { wan_interface: e.target.value })}
                  className="border rounded px-3 py-2 text-sm flex-1"
                />
                <button
                  onClick={() => {
                    setPublicBlocks((prev) => prev.filter((_, idx) => idx !== i));
                    setPreviewCommands(null);
                  }}
                  className="text-xs text-red-600 hover:underline"
                >
                  Quitar
                </button>
              </div>
            ))}
            {publicBlocks.length === 0 && (
              <p className="text-xs text-slate-400">Sin bloques públicos — solo tráfico NATeado.</p>
            )}
          </div>
        </div>

        <div className="flex gap-2 pt-2 border-t">
          <button
            onClick={handlePreview}
            disabled={loading !== null || !lanInterface || wans.some((w) => !w.interface || !w.gateway)}
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
            {loading === "apply" ? "Aplicando..." : "Aplicar cambios"}
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

function StateCard({ title, rows }: { title: string; rows: Record<string, unknown>[] }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-xs font-medium text-slate-500 mb-2">
        {title} ({rows.length})
      </h3>
      <div className="text-xs text-slate-600 max-h-32 overflow-y-auto space-y-1">
        {rows.length === 0 && <p className="text-slate-400">Sin datos.</p>}
        {rows.slice(0, 20).map((row, i) => (
          <div key={i} className="truncate" title={JSON.stringify(row)}>
            {String(row["gateway"] ?? row["action"] ?? row["chain"] ?? row["name"] ?? JSON.stringify(row))}
          </div>
        ))}
      </div>
    </div>
  );
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
