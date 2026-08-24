import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { fetchCurrentUser, logout } from "../api/auth";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/devices", label: "Equipos" },
  { to: "/clients", label: "Clientes" },
  { to: "/plans", label: "Planes" },
  { to: "/billing", label: "Facturación" },
  { to: "/zones", label: "Zonas" },
  { to: "/mapa", label: "Mapa" },
  { to: "/settings", label: "Configuración" },
];

export default function Layout() {
  const navigate = useNavigate();
  const { data: user } = useQuery({ queryKey: ["me"], queryFn: fetchCurrentUser });

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const items = user?.role === "admin" ? [...navItems, { to: "/staff", label: "Personal" }] : navItems;

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 bg-slate-900 text-slate-100 flex flex-col shrink-0">
        <div className="px-4 py-5 text-lg font-semibold border-b border-slate-800">ISP Manager</div>
        <nav className="flex-1 px-2 py-4 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${
                  isActive ? "bg-slate-700 text-white" : "text-slate-300 hover:bg-slate-800"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={handleLogout}
          className="m-2 rounded px-3 py-2 text-sm text-left text-slate-300 hover:bg-slate-800"
        >
          Cerrar sesión
        </button>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
