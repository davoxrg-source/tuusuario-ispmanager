#!/usr/bin/env bash
# Instala ISP Manager en un servidor Linux (Debian/Ubuntu) usando systemd, sin Docker.
# Ejecutar como el usuario dueño de la app (ej. ispapp), con sudo disponible.
#
# Uso: bash deploy/scripts/install.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "== 1/6: Paquetes de sistema (python3-venv, postgresql, nodejs) =="
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip postgresql postgresql-contrib nodejs npm

echo "== 2/6: Base de datos PostgreSQL =="
sudo -u postgres psql -f "$PROJECT_ROOT/deploy/postgres/init.sql" || echo "(rol/BD ya existen, se continúa)"

echo "== 3/6: Entorno virtual del backend =="
cd "$BACKEND_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Generando SECRET_KEY y CREDENTIALS_ENCRYPTION_KEY en .env..."
  SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  sed -i "s#^SECRET_KEY=.*#SECRET_KEY=${SECRET_KEY}#" .env
  sed -i "s#^CREDENTIALS_ENCRYPTION_KEY=.*#CREDENTIALS_ENCRYPTION_KEY=${FERNET_KEY}#" .env
  echo "Revisa $BACKEND_DIR/.env y ajusta DATABASE_URL si cambiaste la contraseña en init.sql."
fi

echo "== 4/6: Migraciones de base de datos =="
alembic upgrade head

echo "== 5/6: Build del frontend =="
cd "$FRONTEND_DIR"
npm install
npm run build

echo "== 6/6: Servicio systemd =="
sudo cp "$PROJECT_ROOT/deploy/systemd/ispmanager-backend.service" /etc/systemd/system/
sudo cp "$PROJECT_ROOT/deploy/systemd/ispmanager-backup.service" /etc/systemd/system/
sudo cp "$PROJECT_ROOT/deploy/systemd/ispmanager-backup.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ispmanager-backend
sudo systemctl enable --now ispmanager-backup.timer

echo
echo "Listo. Verifica con: systemctl status ispmanager-backend"
echo "Backup diario de la base (3am) programado -- ver: systemctl list-timers ispmanager-backup.timer"
echo "Crea el primer usuario admin con:"
echo "  cd $BACKEND_DIR && source .venv/bin/activate && python -m app.cli.seed_admin admin@example.com \"Nombre\" \"contraseña-segura\""
echo "Panel disponible en http://<IP-del-servidor>:8000"
