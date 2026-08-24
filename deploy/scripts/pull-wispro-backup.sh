#!/usr/bin/env bash
# Trae a este servidor (10.100.8.10) el ultimo dump de MySQL de wispro
# (wisprosvr01, 10.100.10.1), como tercer sitio de guarda ademas de los
# 2 NAS a los que wispro ya empuja directamente (ver backup-mysql.sh alli).
#
# El cliente ssh de wispro es de 2009 (OpenSSH 5.3) y no puede autenticar
# contra host keys ed25519 modernas, por eso el flujo es "pull" desde aca
# (cliente moderno) en vez de "push" desde alla.
#
# Uso: bash deploy/scripts/pull-wispro-backup.sh

set -euo pipefail

DEST_DIR="${WISPRO_BACKUP_DIR:-/home/ispapp/backups-remote/wispro}"
RETENTION_DAYS="${WISPRO_BACKUP_RETENTION_DAYS:-15}"

mkdir -p "$DEST_DIR"

scp -O -o BatchMode=yes -o ConnectTimeout=15 \
  wispro:'/backup/backup-mysql-wisprosvr01-*.sql.gz' "$DEST_DIR/"

find "$DEST_DIR" -name "backup-mysql-wisprosvr01-*.sql.gz" -mtime "+$RETENTION_DAYS" -type f -delete

echo "Ultimo backup de wispro en $DEST_DIR: $(ls -t "$DEST_DIR" | head -1)"
