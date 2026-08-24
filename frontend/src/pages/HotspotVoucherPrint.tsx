import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { listHotspotProfiles, listHotspotVouchers } from "../api/hotspot";

function limitsLabel(durationHours: number | null, dataLimitMb: number | null): string {
  const parts: string[] = [];
  if (durationHours) parts.push(`${durationHours}h`);
  if (dataLimitMb) parts.push(`${dataLimitMb}MB`);
  return parts.join(" / ") || "—";
}

export default function HotspotVoucherPrint() {
  const { batchId } = useParams<{ batchId: string }>();
  const id = batchId!;

  const { data: vouchers = [] } = useQuery({
    queryKey: ["hotspot-vouchers", "batch", id],
    queryFn: () => listHotspotVouchers({ batch_id: id }),
  });
  const { data: profiles = [] } = useQuery({ queryKey: ["hotspot-profiles"], queryFn: listHotspotProfiles });

  const profile = profiles.find((p) => p.id === vouchers[0]?.profile_id);

  return (
    <div className="max-w-3xl mx-auto p-8 print:p-0">
      <div className="flex items-center justify-between mb-6 print:hidden">
        <h1 className="text-lg font-semibold text-slate-800">
          Lote de fichas HotSpot ({vouchers.length})
        </h1>
        <button
          onClick={() => window.print()}
          className="bg-slate-900 text-white text-sm rounded px-4 py-2"
        >
          Imprimir
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 print:grid-cols-2">
        {vouchers.map((v) => (
          <div key={v.id} className="border-2 border-dashed rounded-lg p-4 text-center break-inside-avoid">
            <p className="text-xs text-slate-500 uppercase tracking-wide">Ficha HotSpot</p>
            <p className="text-2xl font-mono font-bold tracking-widest my-2">{v.code}</p>
            <p className="text-xs text-slate-600">
              {profile ? limitsLabel(profile.duration_hours, profile.data_limit_mb) : "—"}
            </p>
            <p className="text-sm font-medium">
              {profile?.currency ?? ""} {Number(v.price).toFixed(2)}
            </p>
          </div>
        ))}
        {vouchers.length === 0 && (
          <p className="col-span-2 text-center text-slate-400 py-8">Cargando fichas del lote...</p>
        )}
      </div>
    </div>
  );
}
