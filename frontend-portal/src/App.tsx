import { Route, Routes } from "react-router-dom";
import PortalLayout from "./components/PortalLayout";
import RequireAuth from "./components/RequireAuth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Invoices from "./pages/Invoices";
import Tickets from "./pages/Tickets";
import TicketDetail from "./pages/TicketDetail";
import Profile from "./pages/Profile";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <PortalLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="facturas" element={<Invoices />} />
        <Route path="tickets" element={<Tickets />} />
        <Route path="tickets/:ticketId" element={<TicketDetail />} />
        <Route path="perfil" element={<Profile />} />
      </Route>
    </Routes>
  );
}
