import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  createHotspotProfile,
  deleteHotspotProfile,
  generateVoucherBatch,
  listHotspotProfiles,
  listHotspotVouchers,
  sellVoucher,
  updateHotspotProfile,
  voidVoucher,
} from "../api/hotspot";
import { fetchCurrentUser } from "../api/auth";
import type { HotspotProfile, HotspotProfileInput, HotspotVoucherStatus } from "../api/types";
import Field from "../components/Field";

const emptyProfileForm: HotspotProfileInput = {
  name: "",
  duration_hours: 24,
  data_limit_mb: null,
  price: 0,
  currency: "COP",
};

const statusLabels: Record<HotspotVoucherStatus, string> = {
  unused: "Sin usar",
  sold: "Vendida",
  void: "Anulada",
};

const statusStyles: Record<HotspotVoucherStatus, string> = {
  unused: "bg-slate-100 text-slate-600",
  sold: "bg-green-100 text-green-700",
  void: "bg-red-100 text-red-600",
};

function profileLimitsLabel(profile: HotspotProfile): string {
  const parts: string[] = [];
  if (profile.duration_hours) parts.push(`${profile.duration_hours}h`);
  if (profile.data_limit_mb) parts.push(`${profile.data_limit_mb}MB`);
  return parts.join(" / ") || "—";
}

export default function HotspotVouchers() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useQuery({ queryKey: ["me"], queryFn: fetchCurrentUser });
  const isAdmin = user?.role === "admin";

  const { data: profiles = [] } = useQuery({ queryKey: ["hotspot-profiles"], queryFn: listHotspotProfiles });
  const [statusFilter, setStatusFilter] = useState<HotspotVoucherStatus | "">("");
  const [profileFilter, setProfileFilter] = useState<string>("");
  const { data: vouchers = [] } = useQuery({
    queryKey: ["hotspot-vouchers", profileFilter, statusFilter],
    queryFn: () =>
      listHotspotVouchers({
        profile_id: profileFilter || undefined,
        status_filter: statusFilter || undefined,
      }),
  });

  const [profileForm, setProfileForm] = useState<HotspotProfileInput>(emptyProfileForm);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);

  const [batchProfileId, setBatchProfileId] = useState("");
  const [batchQuantity, setBatchQuantity] = useState(10);

  const createProfileMutation = useMutation({
    mutationFn: createHotspotProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hotspot-profiles"] });
      closeProfileForm();
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo guardar el perfil."),
  });

  const updateProfileMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<HotspotProfileInput> }) =>
      updateHotspotProfile(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hotspot-profiles"] });
      closeProfileForm();
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo guardar el perfil."),
  });

  const deleteProfileMutation = useMutation({
    mutationFn: deleteHotspotProfile,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["hotspot-profiles"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo borrar el perfil."),
  });

  const batchMutation = useMutation({
    mutationFn: () => generateVoucherBatch(batchProfileId, batchQuantity),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["hotspot-vouchers"] });
      if (created.length > 0) navigate(`/hotspot/lotes/${created[0].batch_id}/imprimir`);
    },
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo generar el lote."),
  });

  const sellMutation = useMutation({
    mutationFn: sellVoucher,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["hotspot-vouchers"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo vender la ficha."),
  });

  const voidMutation = useMutation({
    mutationFn: voidVoucher,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["hotspot-vouchers"] }),
    onError: (err) => alert(axiosErrorMessage(err) ?? "No se pudo anular la ficha."),
  });

  function closeProfileForm() {
    setProfileForm(emptyProfileForm);
    setEditingProfileId(null);
    setShowProfileForm(false);
  }

  function startEditProfile(profile: HotspotProfile) {
    setProfileForm({
      name: profile.name,
      duration_hours: profile.duration_hours,
      data_limit_mb: profile.data_limit_mb,
      price: profile.price,
      currency: profile.currency,
    });
    setEditingProfileId(profile.id);
    setShowProfileForm(true);
  }

  function handleProfileSubmit(e: FormEvent) {
    e.preventDefault();
    if (editingProfileId) {
      updateProfileMutation.mutate({ id: editingProfileId, payload: profileForm });
    } else {
      createProfileMutation.mutate(profileForm);
    }
  }

  function handleBatchSubmit(e: FormEvent) {
    e.preventDefault();
    if (!batchProfileId) return;
    batchMutation.mutate();
  }

  function profileName(id: string): string {
    return profiles.find((p) => p.id === id)?.name ?? "—";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Fichas HotSpot</h1>

      {/* Perfiles */}
      {isAdmin && (
        <div className="bg-white rounded-lg shadow p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-slate-600">Perfiles</h2>
            <button
              onClick={() => (showProfileForm ? closeProfileForm() : setShowProfileForm(true))}
              className="text-xs text-blue-600 hover:underline"
            >
              {showProfileForm ? "Cancelar" : "Nuevo perfil"}
            </button>
          </div>
          {showProfileForm && (
            <form onSubmit={handleProfileSubmit} className="grid grid-cols-2 gap-3 mb-4">
              <Field label="Nombre">
                <input
                  required
                  value={profileForm.name}
                  onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                  className="border rounded px-3 py-2 text-sm w-full"
                />
              </Field>
              <Field label="Precio">
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  value={profileForm.price}
                  onChange={(e) => setProfileForm({ ...profileForm, price: Number(e.target.value) })}
                  className="border rounded px-3 py-2 text-sm w-full"
                />
              </Field>
              <Field label="Duración (horas)" hint="Dejar vacío si la ficha solo limita por datos.">
                <input
                  type="number"
                  min={0}
                  value={profileForm.duration_hours ?? ""}
                  onChange={(e) =>
                    setProfileForm({
                      ...profileForm,
                      duration_hours: e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                  className="border rounded px-3 py-2 text-sm w-full"
                />
              </Field>
              <Field label="Límite de datos (MB)" hint="Dejar vacío si la ficha solo limita por tiempo.">
                <input
                  type="number"
                  min={0}
                  value={profileForm.data_limit_mb ?? ""}
                  onChange={(e) =>
                    setProfileForm({
                      ...profileForm,
                      data_limit_mb: e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                  className="border rounded px-3 py-2 text-sm w-full"
                />
              </Field>
              <button
                type="submit"
                disabled={createProfileMutation.isPending || updateProfileMutation.isPending}
                className="col-span-2 bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
              >
                {editingProfileId ? "Actualizar perfil" : "Guardar perfil"}
              </button>
            </form>
          )}
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">Nombre</th>
                <th className="py-1">Otorga</th>
                <th className="py-1">Precio</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="py-1">{p.name}</td>
                  <td className="py-1">{profileLimitsLabel(p)}</td>
                  <td className="py-1">
                    {p.currency} {Number(p.price).toFixed(2)}
                  </td>
                  <td className="py-1 space-x-2">
                    <button onClick={() => startEditProfile(p)} className="text-xs text-blue-600 hover:underline">
                      Editar
                    </button>
                    <button
                      onClick={() => deleteProfileMutation.mutate(p.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
              {profiles.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-slate-400">
                    Aún no hay perfiles.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Generar lote */}
      <div className="bg-white rounded-lg shadow p-5">
        <h2 className="text-sm font-medium text-slate-600 mb-3">Generar lote de fichas</h2>
        <form onSubmit={handleBatchSubmit} className="flex items-end gap-3">
          <Field label="Perfil">
            <select
              required
              value={batchProfileId}
              onChange={(e) => setBatchProfileId(e.target.value)}
              className="border rounded px-3 py-2 text-sm bg-white"
            >
              <option value="">Seleccionar...</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Cantidad">
            <input
              type="number"
              min={1}
              max={500}
              value={batchQuantity}
              onChange={(e) => setBatchQuantity(Number(e.target.value))}
              className="border rounded px-3 py-2 text-sm w-24"
            />
          </Field>
          <button
            type="submit"
            disabled={batchMutation.isPending || !batchProfileId}
            className="bg-slate-900 text-white text-sm rounded px-4 py-2 disabled:opacity-50"
          >
            Generar e imprimir
          </button>
        </form>
      </div>

      {/* Fichas */}
      <div className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-slate-600">Fichas</h2>
          <div className="flex gap-2">
            <select
              value={profileFilter}
              onChange={(e) => setProfileFilter(e.target.value)}
              className="border rounded px-2 py-1 text-xs bg-white"
            >
              <option value="">Todos los perfiles</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as HotspotVoucherStatus | "")}
              className="border rounded px-2 py-1 text-xs bg-white"
            >
              <option value="">Todos los estados</option>
              <option value="unused">Sin usar</option>
              <option value="sold">Vendida</option>
              <option value="void">Anulada</option>
            </select>
          </div>
        </div>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">Código</th>
              <th className="py-1">Perfil</th>
              <th className="py-1">Precio</th>
              <th className="py-1">Estado</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody>
            {vouchers.map((v) => (
              <tr key={v.id} className="border-t">
                <td className="py-1 font-mono">{v.code}</td>
                <td className="py-1">{profileName(v.profile_id)}</td>
                <td className="py-1">{Number(v.price).toFixed(2)}</td>
                <td className="py-1">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${statusStyles[v.status]}`}>
                    {statusLabels[v.status]}
                  </span>
                </td>
                <td className="py-1 space-x-2">
                  {v.status === "unused" && (
                    <button
                      onClick={() => sellMutation.mutate(v.id)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Vender
                    </button>
                  )}
                  {isAdmin && v.status !== "void" && (
                    <button
                      onClick={() => voidMutation.mutate(v.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Anular
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {vouchers.length === 0 && (
              <tr>
                <td colSpan={5} className="py-4 text-center text-slate-400">
                  Ninguna ficha con estos filtros.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function axiosErrorMessage(err: unknown): string | null {
  if (typeof err === "object" && err !== null && "response" in err) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}
