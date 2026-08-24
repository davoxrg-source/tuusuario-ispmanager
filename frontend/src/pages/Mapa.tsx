import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import iconRetinaUrl from "leaflet/dist/images/marker-icon-2x.png";
import iconUrl from "leaflet/dist/images/marker-icon.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";
import { listClients } from "../api/clients";
import { listDevices } from "../api/devices";
import { listZones } from "../api/zones";

// Leaflet arma la URL de los íconos por defecto asumiendo una estructura de
// assets que Vite no replica -- sin esto, los marcadores salen rotos (sin
// ícono). Fix estándar y conocido, no es un bug propio.
L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

// Leaflet solo trae el pin azul por defecto (sin variantes de color) -- en
// vez de sumar más imágenes, un punto de color simple con CSS alcanza para
// distinguir cliente de equipo de un vistazo.
function dotIcon(color: string) {
  return L.divIcon({
    html: `<span style="display:block;width:16px;height:16px;border-radius:9999px;background:${color};border:2px solid white;box-shadow:0 0 2px rgba(0,0,0,0.5)"></span>`,
    className: "",
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -8],
  });
}

const clientIcon = dotIcon("#2563eb"); // azul
const deviceIcon = dotIcon("#ea580c"); // naranja

// Tuluá/Palmira, Valle del Cauca -- centro por defecto cuando todavía no hay
// ningún marcador cargado (mejor que arrancar en el (0,0) del Atlántico).
const DEFAULT_CENTER: [number, number] = [3.85, -76.35];

export default function Mapa() {
  const { data: clients = [] } = useQuery({ queryKey: ["clients"], queryFn: listClients });
  const { data: devices = [] } = useQuery({ queryKey: ["devices"], queryFn: listDevices });
  const { data: zones = [] } = useQuery({ queryKey: ["zones"], queryFn: listZones });
  const [zoneFilter, setZoneFilter] = useState("");

  const clientsWithLocation = useMemo(
    () =>
      clients.filter(
        (c) =>
          c.latitude != null && c.longitude != null && (!zoneFilter || c.zone_id === zoneFilter),
      ),
    [clients, zoneFilter],
  );
  const devicesWithLocation = useMemo(
    () =>
      devices.filter(
        (d) =>
          d.latitude != null && d.longitude != null && (!zoneFilter || d.zone_id === zoneFilter),
      ),
    [devices, zoneFilter],
  );

  const firstPoint = clientsWithLocation[0] ?? devicesWithLocation[0];
  const center: [number, number] = firstPoint
    ? [Number(firstPoint.latitude), Number(firstPoint.longitude)]
    : DEFAULT_CENTER;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Mapa</h1>
        <select
          value={zoneFilter}
          onChange={(e) => setZoneFilter(e.target.value)}
          className="border rounded px-3 py-2 text-sm bg-white"
        >
          <option value="">Todas las zonas</option>
          {zones.map((zone) => (
            <option key={zone.id} value={zone.id}>
              {zone.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-600" /> Clientes (
          {clientsWithLocation.length})
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-orange-600" /> Equipos (
          {devicesWithLocation.length})
        </span>
        <span className="text-slate-400">
          Los que no tienen coordenadas no aparecen acá — se cargan desde el formulario de edición de
          cada uno.
        </span>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden" style={{ height: "70vh" }}>
        <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {clientsWithLocation.map((client) => (
            <Marker
              key={`client-${client.id}`}
              position={[Number(client.latitude), Number(client.longitude)]}
              icon={clientIcon}
            >
              <Popup>
                <strong>{client.full_name}</strong>
                <br />
                {client.address ?? "Sin dirección"}
                <br />
                Estado: {client.status}
              </Popup>
            </Marker>
          ))}
          {devicesWithLocation.map((device) => (
            <Marker
              key={`device-${device.id}`}
              position={[Number(device.latitude), Number(device.longitude)]}
              icon={deviceIcon}
            >
              <Popup>
                <strong>{device.name}</strong>
                <br />
                {device.site ?? "Sin sitio"}
                <br />
                Estado: {device.status}
                <br />
                <Link to={`/devices/${device.id}`} className="text-blue-600 hover:underline">
                  Ver detalle
                </Link>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
