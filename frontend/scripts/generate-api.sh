#!/usr/bin/env bash
# Regenerates src/app/core/api/schema.d.ts from the backend's OpenAPI schema.
#
# Generates the schema through `manage.py spectacular` into a temp file
# instead of fetching it from a running dev server: no live backend needed,
# so this works the same in CI as on a laptop.
set -euo pipefail

frontend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$frontend_dir/../backend"
schema_file="$(mktemp -t lorebase-openapi).yaml"

(cd "$backend_dir" && uv run python manage.py spectacular --file "$schema_file")

npx openapi-typescript "$schema_file" -o "$frontend_dir/src/app/core/api/schema.d.ts"
rm -f "$schema_file"

echo "Generated src/app/core/api/schema.d.ts"
