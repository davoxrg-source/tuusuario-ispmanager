import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Devices from "./pages/Devices";
import DeviceDetail from "./pages/DeviceDetail";
import Clients from "./pages/Clients";
import Plans from "./pages/Plans";
import Billing from "./pages/Billing";
import Settings from "./pages/Settings";
import Zones from "./pages/Zones";
import Staff from "./pages/Staff";
import Mapa from "./pages/Mapa";
import Almacen from "./pages/Almacen";
import Instalaciones from "./pages/Instalaciones";
import OrdenInstalacion from "./pages/OrdenInstalacion";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* Fuera del <Layout> a propósito -- es una vista pensada para
          imprimirse, no debe salir el sidebar de navegación. Sigue
          requiriendo sesión vía RequireAuth. */}
      <Route
        path="/instalaciones/:installationId/orden"
        element={
          <RequireAuth>
            <OrdenInstalacion />
          </RequireAuth>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="devices" element={<Devices />} />
        <Route path="devices/:deviceId" element={<DeviceDetail />} />
        <Route path="clients" element={<Clients />} />
        <Route path="plans" element={<Plans />} />
        <Route path="billing" element={<Billing />} />
        <Route path="zones" element={<Zones />} />
        <Route path="staff" element={<Staff />} />
        <Route path="mapa" element={<Mapa />} />
        <Route path="almacen" element={<Almacen />} />
        <Route path="instalaciones" element={<Instalaciones />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
