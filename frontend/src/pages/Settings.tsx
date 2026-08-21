import { useQuery } from "@tanstack/react-query";
import { fetchCurrentUser } from "../api/auth";

export default function Settings() {
  const { data: user } = useQuery({ queryKey: ["me"], queryFn: fetchCurrentUser });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Configuración</h1>
      <div className="bg-white rounded-lg shadow p-5 max-w-md">
        <h2 className="text-sm font-medium text-slate-600 mb-3">Sesión actual</h2>
        {user ? (
          <dl className="text-sm space-y-1">
            <div className="flex justify-between">
              <dt className="text-slate-500">Nombre</dt>
              <dd>{user.full_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Correo</dt>
              <dd>{user.email}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Rol</dt>
              <dd>{user.role}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-sm text-slate-400">Cargando...</p>
        )}
      </div>
    </div>
  );
}
