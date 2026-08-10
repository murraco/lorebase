#!/usr/bin/env bash
set -euo pipefail

# Usage: COMPOSE_FILE=docker-compose.prod.yml ENV_FILE=.env.prod ./backup.sh [output-file]
#
# Dumps the Lorebase database to a single compressed, custom-format file
# (-Fc), via `docker compose exec` -- no pg_dump/psql needed on the host,
# only inside the db container, which already has them. pgvector columns
# need nothing special here: pg_dump handles extension types
# transparently, as long as `CREATE EXTENSION vector` has already run on
# the restore target (postgres/init.sql does this on every fresh db).
#
# Defaults to the dev stack; point COMPOSE_FILE/ENV_FILE at the prod ones
# for a real backup.

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"

cd "$INFRA_DIR"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

OUTPUT="${1:-backups/lorebase-$(date +%Y%m%dT%H%M%S).dump}"
mkdir -p "$(dirname "$OUTPUT")"

docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc > "$OUTPUT"

echo "Backup written to $INFRA_DIR/$OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
