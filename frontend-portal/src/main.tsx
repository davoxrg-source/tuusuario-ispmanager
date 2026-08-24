import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Registra el service worker de push (ver public/sw.js) -- guardado detrás
// de la feature-check, algunos navegadores/contextos (ej. http sin TLS) no
// lo soportan y no debe romper el resto de la app.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/portal/sw.js").catch((err) => {
    console.warn("No se pudo registrar el service worker de push:", err);
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* basename="/portal" -- este bundle se sirve montado en /portal
          (ver app.mount("/portal", ...) en backend/app/main.py), separado
          del bundle de staff que vive en /. */}
      <BrowserRouter basename="/portal">
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
