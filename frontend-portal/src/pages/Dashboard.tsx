import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchMyProfile } from "../api/auth";
import { listMyInvoices } from "../api/portal";

const statusLabels: Record<string, string> = {
  active: "Activo",
  suspended: "Suspendido",
  cancelled: "Cancelado",
};

export default function Dashboard() {
  const { data: profile } = useQuery({ queryKey: ["me"], queryFn: fetchMyProfile });
  const { data: invoices = [] } = useQuery({ queryKey: ["my-invoices"], queryFn: listMyInvoices });

  const pending = invoices.filter((i) => i.status === "pending" || i.status === "overdue");
  const pendingTotal = pending.reduce((sum, i) => sum + Number(i.amount) + Number(i.late_fee_amount), 0);

  if (!profile) return <p className="text-sm text-slate-500">Cargando...</p>;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-5">
        <h1 className="text-lg font-semibold text-slate-800">Hola, {profile.full_name.split(" ")[0]}</h1>
        <p className="text-sm text-slate-500 mt-1">
          Estado del servicio:{" "}
          <span
            className={
              profile.status === "active" ? "text-green-600 font-medium" : "text-amber-600 font-medium"
            }
          >
            {statusLabels[profile.status]}
          </span>
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Conexión: {profile.is_online ? "en línea ahora" : "sin conexión"}
        </p>
      </div>

      {profile.status === "suspended" && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
          Tu servicio está suspendido por falta de pago. Reportá tu pago desde{" "}
          <Link to="/facturas" className="underline">
            Facturas
          </Link>{" "}
          para reactivarlo.
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-medium text-slate-600 mb-1">Saldo pendiente</h2>
        <p className="text-2xl font-semibold text-slate-800">${pendingTotal.toFixed(2)}</p>
        <p className="text-xs text-slate-400 mt-1">
          {pending.length === 0 ? "Estás al día." : `${pending.length} factura(s) sin pagar`}
        </p>
        <Link to="/facturas" className="text-xs text-blue-600 hover:underline mt-2 inline-block">
          Ver facturas →
        </Link>
      </div>
    </div>
  );
}
