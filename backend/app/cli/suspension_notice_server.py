"""Servidor HTTP mínimo, standalone (sin FastAPI, sin dependencias nuevas)
que muestra el aviso de suspensión a cualquier cliente cuyo tráfico HTTP el
router redirige acá (ver app/services/mikrotik/suspension.py). Catch-all:
no importa qué Host/path pida el cliente, siempre devuelve la misma página
-- un puerto dedicado, aparte del backend principal (puerto 8000), porque
el DNAT del router preserva el Host/path original de la request, y
redirigir al backend normal haría caer esa request en el catch-all de la
SPA de staff en vez de mostrar el aviso.

Uso: python -m app.cli.suspension_notice_server
"""

import http.server
import os

PORTAL_LOGIN_URL = os.environ.get("PORTAL_LOGIN_URL", "http://10.100.8.10:8000/portal/login")
PORT = int(os.environ.get("SUSPENSION_NOTICE_PORT", "8095"))

_HTML = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Servicio suspendido</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #f1f5f9;
    display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 32px; max-width: 420px;
    text-align: center; }}
  h1 {{ font-size: 20px; margin-bottom: 12px; }}
  p {{ color: #94a3b8; font-size: 14px; line-height: 1.5; }}
  a.button {{ display: inline-block; margin-top: 20px; background: #f1f5f9; color: #0f172a;
    padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Tu servicio está suspendido por falta de pago</h1>
    <p>Ingresá al portal de clientes para ver el detalle de tu factura y pagarla en línea.</p>
    <a class="button" href="{PORTAL_LOGIN_URL}">Ir al portal</a>
  </div>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def _respond(self) -> None:
        body = _HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._respond()

    def do_POST(self) -> None:
        self._respond()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


if __name__ == "__main__":
    http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
