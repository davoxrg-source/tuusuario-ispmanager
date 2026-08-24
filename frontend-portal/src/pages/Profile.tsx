import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { changePassword, fetchMyProfile } from "../api/auth";
import { updateMyProfile } from "../api/portal";
import { disablePush, enablePush, getCurrentPushSubscription, isPushSupported } from "../api/push";

export default function Profile() {
  const queryClient = useQueryClient();
  const { data: profile } = useQuery({ queryKey: ["me"], queryFn: fetchMyProfile });
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);

  const [pushSubscribed, setPushSubscribed] = useState(false);
  const [pushError, setPushError] = useState<string | null>(null);
  const [pushLoading, setPushLoading] = useState(false);

  useEffect(() => {
    if (profile) {
      setPhone(profile.phone ?? "");
      setEmail(profile.email ?? "");
      setAddress(profile.address ?? "");
    }
  }, [profile]);

  useEffect(() => {
    getCurrentPushSubscription().then((sub) => setPushSubscribed(Boolean(sub)));
  }, []);

  async function handleTogglePush() {
    setPushError(null);
    setPushLoading(true);
    try {
      if (pushSubscribed) {
        await disablePush();
        setPushSubscribed(false);
      } else {
        await enablePush();
        setPushSubscribed(true);
      }
    } catch (err) {
      setPushError(err instanceof Error ? err.message : "No se pudo activar las notificaciones.");
    } finally {
      setPushLoading(false);
    }
  }

  const profileMutation = useMutation({
    mutationFn: () => updateMyProfile({ phone, email, address }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setSavedMessage("Datos actualizados.");
    },
  });

  const passwordMutation = useMutation({
    mutationFn: () => changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setPasswordSaved(true);
      setPasswordError(null);
      setCurrentPassword("");
      setNewPassword("");
    },
    onError: () => setPasswordError("La contraseña actual no es correcta."),
  });

  function handleProfileSubmit(e: FormEvent) {
    e.preventDefault();
    setSavedMessage(null);
    profileMutation.mutate();
  }

  function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setPasswordSaved(false);
    passwordMutation.mutate();
  }

  if (!profile) return <p className="text-sm text-slate-500">Cargando...</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-slate-800">Mi perfil</h1>

      <form onSubmit={handleProfileSubmit} className="bg-white rounded-lg shadow p-4 space-y-3">
        <p className="text-xs text-slate-400">
          {profile.full_name} · doc. {profile.identification ?? "—"}
        </p>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Teléfono</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Correo</label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Dirección</label>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>
        {savedMessage && <p className="text-xs text-green-600">{savedMessage}</p>}
        <button
          type="submit"
          disabled={profileMutation.isPending}
          className="w-full bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
        >
          Guardar
        </button>
      </form>

      {isPushSupported() && (
        <div className="bg-white rounded-lg shadow p-4 space-y-2">
          <h2 className="text-sm font-medium text-slate-600">Notificaciones push</h2>
          <p className="text-xs text-slate-400">
            Recibí avisos en este dispositivo cuando confirmemos un pago o respondamos un ticket.
          </p>
          {pushError && <p className="text-xs text-red-600">{pushError}</p>}
          <button
            onClick={handleTogglePush}
            disabled={pushLoading}
            className="w-full bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
          >
            {pushSubscribed ? "Desactivar notificaciones" : "Activar notificaciones"}
          </button>
        </div>
      )}

      <form onSubmit={handlePasswordSubmit} className="bg-white rounded-lg shadow p-4 space-y-3">
        <h2 className="text-sm font-medium text-slate-600">Cambiar contraseña</h2>
        <input
          type="password"
          required
          placeholder="Contraseña actual"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
        />
        <input
          type="password"
          required
          placeholder="Contraseña nueva"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          className="w-full border rounded px-3 py-2 text-sm"
        />
        {passwordError && <p className="text-xs text-red-600">{passwordError}</p>}
        {passwordSaved && <p className="text-xs text-green-600">Contraseña actualizada.</p>}
        <button
          type="submit"
          disabled={passwordMutation.isPending}
          className="w-full bg-slate-900 text-white text-sm rounded py-2 disabled:opacity-50"
        >
          Cambiar contraseña
        </button>
      </form>
    </div>
  );
}
