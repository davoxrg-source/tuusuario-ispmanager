import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getInstallation } from "../api/installations";
import { listClients } from "../api/clients";
import { listPlans } from "../api/plans";
import { listStaffDirectory } from "../api/users";

const statusLabels: Record<string, string> = {
  scheduled: "Programada",
  completed: "Completada",
  cancelled: "Cancelada",
};

export default function OrdenInstalacion() {
  const { installationId } = useParams<{ installationId: string }>();
  const id = installationId!;

  const { data: installation } = useQuery({
    queryKey: ["installation", id],
    queryFn: () => getInstallation(id),
  });
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: plans = [] } = useQuery({ queryKey: ["plans"], queryFn: listPlans });
  const { data: technicians = [] } = useQuery({
    queryKey: ["staff-directory"],
    queryFn: listStaffDirectory,
  });

  if (!installation) return <p className="p-6 text-sm text-slate-500">Cargando...</p>;

  const client = clients.find((c) => c.id === installation.client_id);
  const plan = plans.find((p) => p.id === client?.plan_id);
  const technician = technicians.find((t) => t.id === installation.assigned_technician_id);

  return (
    <div className="max-w-2xl mx-auto p-8 print:p-0">
      <div className="flex items-center justify-between mb-6 print:hidden">
        <h1 className="text-lg font-semibold text-slate-800">Orden de trabajo</h1>
        <button
          onClick={() => window.print()}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2"
        >
          Imprimir
        </button>
      </div>

      <div className="border rounded-lg p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Orden de instalación</h2>
          <p className="text-sm text-slate-500">Fecha programada: {installation.scheduled_date}</p>
          <p className="text-sm text-slate-500">Estado: {statusLabels[installation.status]}</p>
        </div>

        <div className="border-t pt-4">
          <h3 className="text-sm font-medium text-slate-600 mb-1">Cliente</h3>
          <p className="text-sm">{client?.full_name ?? "—"}</p>
          <p className="text-sm text-slate-500">{client?.address ?? "Sin dirección registrada"}</p>
          <p className="text-sm text-slate-500">{client?.phone ?? "Sin teléfono registrado"}</p>
        </div>

        <div className="border-t pt-4">
          <h3 className="text-sm font-medium text-slate-600 mb-1">Servicio</h3>
          <p className="text-sm">
            Plan: {plan ? `${plan.name} (${plan.download_speed_mbps}/${plan.upload_speed_mbps} Mbps)` : "—"}
          </p>
          <p className="text-sm">Técnico asignado: {technician?.full_name ?? "Sin asignar"}</p>
        </div>

        {installation.notes && (
          <div className="border-t pt-4">
            <h3 className="text-sm font-medium text-slate-600 mb-1">Notas</h3>
            <p className="text-sm whitespace-pre-wrap">{installation.notes}</p>
          </div>
        )}
      </div>
    </div>
  );
}
