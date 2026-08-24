// Service worker del portal de cliente -- solo maneja push notifications,
// nada de cacheo offline (fuera de alcance por ahora). Se sirve en
// /portal/sw.js (Vite copia public/ tal cual a la raíz del dist), así que
// su scope por defecto es /portal/ -- exactamente donde vive esta app.

self.addEventListener("push", (event) => {
  let payload = { title: "ISP Manager", body: "" };
  try {
    payload = event.data.json();
  } catch {
    payload.body = event.data ? event.data.text() : "";
  }
  event.waitUntil(self.registration.showNotification(payload.title, { body: payload.body }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes("/portal") && "focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow("/portal/");
    }),
  );
});
