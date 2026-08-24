import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { logout } from "../api/auth";

const navItems = [
  { to: "/", label: "Inicio", end: true },
  { to: "/facturas", label: "Facturas" },
  { to: "/tickets", label: "Soporte" },
  { to: "/perfil", label: "Perfil" },
];

export default function PortalLayout() {
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-slate-900 text-white px-4 py-3 flex items-center justify-between">
        <span className="font-semibold text-sm">Mi Cuenta</span>
        <button onClick={handleLogout} className="text-xs text-slate-300 hover:underline">
          Cerrar sesión
        </button>
      </header>
      <main className="flex-1 p-4 pb-20 max-w-md w-full mx-auto">
        <Outlet />
      </main>
      <nav className="fixed bottom-0 inset-x-0 bg-white border-t flex justify-around py-2 max-w-md mx-auto w-full">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `text-xs px-3 py-1 rounded ${isActive ? "text-slate-900 font-medium" : "text-slate-400"}`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
