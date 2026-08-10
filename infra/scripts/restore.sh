#!/usr/bin/env bash
set -euo pipefail

# Usage: COMPOSE_FILE=docker-compose.prod.yml ENV_FILE=.env.prod ./restore.sh <dump-file>
#
# Restores a backup made by backup.sh into the db service defined by
# COMPOSE_FILE. Destructive by design (--clean drops existing objects
# before recreating them, so the target ends up exactly matching the
# dump) -- asks for explicit confirmation before touching anything.

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"

cd "$INFRA_DIR"

if [ $# -ne 1 ]; then
  echo "Usage: $0 <dump-file>" >&2
  exit 1
fi
DUMP_FILE="$1"
if [ ! -f "$DUMP_FILE" ]; then
  echo "No such file: $DUMP_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "This will DROP and recreate objects in database '${POSTGRES_DB}'"
echo "on the db service from ${COMPOSE_FILE}, replacing them with the contents of ${DUMP_FILE}."
read -r -p "Type 'yes' to continue: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --clean --if-exists < "$DUMP_FILE"

echo "Restore complete."
