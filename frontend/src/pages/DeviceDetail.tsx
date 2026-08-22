import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getActiveSessions, getDevice, getDeviceMetrics, getDeviceStatus } from "../api/devices";
import InterfaceConfig from "../components/InterfaceConfig";
import QosPlans from "../components/QosPlans";
import WanBalancing from "../components/WanBalancing";

export default function DeviceDetail() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const id = deviceId!;

  const { data: device } = useQuery({ queryKey: ["device", id], queryFn: () => getDevice(id) });
  const { data: status } = useQuery({
    queryKey: ["device-status", id],
    queryFn: () => getDeviceStatus(id),
    refetchInterval: 15000,
    retry: false,
  });
  const { data: metrics = [] } = useQuery({
    queryKey: ["device-metrics", id],
    queryFn: () => getDeviceMetrics(id, 100),
  });
  const { data: sessions = [] } = useQuery({
    queryKey: ["device-sessions", id],
    queryFn: () => getActiveSessions(id),
    refetchInterval: 15000,
    retry: false,
  });

  const chartData = [...metrics]
    .reverse()
    .map((m) => ({
      time: new Date(m.recorded_at).toLocaleTimeString(),
      cpu: m.cpu_load_percent ?? 0,
      sessions: m.active_ppp_sessions ?? 0,
    }));

  if (!device) return <p className="text-sm text-slate-500">Cargando...</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/devices" className="text-sm text-blue-600 hover:underline">
          ← Volver a equipos
        </Link>
        <h1 className="text-xl font-semibold text-slate-800 mt-1">{device.name}</h1>
        <p className="text-sm text-slate-500">
          {device.host} · {device.site ?? "sin sitio"}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="CPU" value={status ? `${status.cpu_load_percent ?? "—"}%` : "—"} />
        <Metric
          label="Memoria"
          value={
            status?.memory_total_bytes
              ? `${Math.round(((status.memory_used_bytes ?? 0) / status.memory_total_bytes) * 100)}%`
              : "—"
          }
        />
        <Metric
          label="Uptime"
          value={status?.uptime_seconds ? formatUptime(status.uptime_seconds) : "—"}
        />
        <Metric label="Sesiones PPP activas" value={status?.active_ppp_sessions ?? "—"} />
      </div>

      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-medium text-slate-600 mb-3">Histórico de CPU / sesiones activas</h2>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" hide />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="cpu" stroke="#0f172a" dot={false} name="CPU %" />
            <Line type="monotone" dataKey="sessions" stroke="#2563eb" dot={false} name="Sesiones PPP" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <h2 className="text-sm font-medium text-slate-600 px-5 pt-4">Sesiones PPPoE activas</h2>
        <table className="w-full text-sm mt-2">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2">Usuario</th>
              <th className="px-4 py-2">Dirección IP</th>
              <th className="px-4 py-2">Uptime</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.name} className="border-t">
                <td className="px-4 py-2">{s.name}</td>
                <td className="px-4 py-2">{s.address ?? "—"}</td>
                <td className="px-4 py-2">{s.uptime ?? "—"}</td>
              </tr>
            ))}
            {sessions.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400">
                  Sin sesiones activas o equipo no accesible.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <InterfaceConfig deviceId={id} />
      <WanBalancing deviceId={id} />
      <QosPlans deviceId={id} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-semibold text-slate-800">{value}</p>
    </div>
  );
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${days}d ${hours}h ${minutes}m`;
}
