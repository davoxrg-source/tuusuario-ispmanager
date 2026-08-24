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
