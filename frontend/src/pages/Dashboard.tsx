import { useQuery } from "@tanstack/react-query";
import { listDevices } from "../api/devices";
import { listClients } from "../api/clients";
import { listInvoices } from "../api/billing";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-semibold text-slate-800 mt-1">{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: listDevices });
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: invoices = [] } = useQuery({ queryKey: ["invoices"], queryFn: listInvoices });

  const onlineDevices = devices.filter((d) => d.status === "online").length;
  const activeClients = clients.filter((c) => c.status === "active").length;
  const suspendedClients = clients.filter((c) => c.status === "suspended").length;
  const now = new Date();
  const revenueThisMonth = invoices
    .filter((inv) => {
      const paidAt = inv.paid_at ? new Date(inv.paid_at) : null;
      return (
        inv.status === "paid" &&
        paidAt &&
        paidAt.getMonth() === now.getMonth() &&
        paidAt.getFullYear() === now.getFullYear()
      );
    })
    .reduce((sum, inv) => sum + Number(inv.amount), 0);
  const overdueInvoices = invoices.filter((inv) => inv.status === "overdue").length;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Equipos en línea" value={`${onlineDevices} / ${devices.length}`} />
        <StatCard label="Clientes activos" value={activeClients} />
        <StatCard label="Clientes suspendidos" value={suspendedClients} />
        <StatCard label="Facturas vencidas" value={overdueInvoices} />
        <StatCard label="Ingresos del mes" value={`$${revenueThisMonth.toFixed(2)}`} />
      </div>
    </div>
  );
}
