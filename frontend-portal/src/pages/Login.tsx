import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth";

export default function Login() {
  const [identification, setIdentification] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(identification, password);
      navigate("/");
    } catch {
      setError("Número de identificación o contraseña incorrectos.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 px-4">
      <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-8 w-full max-w-sm space-y-4">
        <h1 className="text-xl font-semibold text-slate-800">Mi Cuenta</h1>
        <div>
          <label className="block text-sm text-slate-600 mb-1">Número de identificación</label>
          <input
            required
            value={identification}
            onChange={(e) => setIdentification(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-600 mb-1">Contraseña</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-slate-900 text-white rounded py-2 text-sm font-medium disabled:opacity-50"
        >
          {loading ? "Ingresando..." : "Ingresar"}
        </button>
        <p className="text-xs text-slate-400 text-center">
          ¿No tenés acceso todavía? Pedile al equipo de soporte que active tu portal.
        </p>
      </form>
    </div>
  );
}
