#!/usr/bin/env bash
# Backup diario de la base de datos de ispmanager (Postgres) -- pg_dump
# comprimido, con retención automática. Pensado para correr por systemd
# timer (ver deploy/systemd/ispmanager-backup.timer) o cron.
#
# Lee la conexión de backend/.env (DATABASE_URL) -- no hace falta pasarle
# credenciales aparte.
#
# Uso: bash deploy/scripts/backup-db.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
BACKUP_DIR="${ISPMANAGER_BACKUP_DIR:-$PROJECT_ROOT/backups}"
RETENTION_DAYS="${ISPMANAGER_BACKUP_RETENTION_DAYS:-15}"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "No se encontró $BACKEND_DIR/.env -- no se puede leer DATABASE_URL." >&2
  exit 1
fi

DATABASE_URL=$(grep -E '^DATABASE_URL=' "$BACKEND_DIR/.env" | head -1 | cut -d= -f2-)
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL vacía en $BACKEND_DIR/.env" >&2
  exit 1
fi

# postgresql+psycopg://user:pass@host:port/dbname -> variables sueltas.
# Se resuelve con Python (ya es dependencia dura de este proyecto) leyendo
# la URL de una variable de entorno, no interpolada en el código -- así no
# se rompe si la contraseña tiene comillas u otros caracteres especiales.
eval "$(ISPMANAGER_DB_URL="$DATABASE_URL" "$BACKEND_DIR/.venv/bin/python3" -c "
import os
from urllib.parse import urlparse
u = urlparse(os.environ['ISPMANAGER_DB_URL'].replace('postgresql+psycopg', 'postgresql', 1))
print(f'PGUSER={u.username}')
print(f'PGPASSWORD={u.password}')
print(f'PGHOST={u.hostname}')
print(f'PGPORT={u.port or 5432}')
print(f'PGDATABASE={u.path.lstrip(chr(47))}')
")"
export PGUSER PGPASSWORD PGHOST PGPORT PGDATABASE

mkdir -p "$BACKUP_DIR"
backup_file="$BACKUP_DIR/ispmanager-$(hostname)-$(date +%Y-%m-%d_%H%M).sql.gz"

pg_dump | gzip > "$backup_file"
echo "Backup creado: $backup_file ($(du -h "$backup_file" | cut -f1))"

find "$BACKUP_DIR" -name "ispmanager-$(hostname)-*.sql.gz" -mtime "+$RETENTION_DAYS" -type f -delete
