#!/usr/bin/env bash
# Create the atlas_research PostgreSQL database and run table init.
# Run once on a fresh environment.
#
# Usage:
#   ./scripts/create_db.sh
#
# Expects DATABASE_URL in environment or .env file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env if present
if [ -f "$ROOT_DIR/.env" ]; then
  export $(grep -v '^#' "$ROOT_DIR/.env" | xargs)
fi

DB_URL="${DATABASE_URL:-postgresql://atlas:password@localhost:5433/atlas_research}"

# Extract components for createdb
DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$DB_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_USER=$(echo "$DB_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_NAME=$(echo "$DB_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

echo "Creating database: $DB_NAME on $DB_HOST:$DB_PORT"

# Create DB if it doesn't exist
createdb \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  "$DB_NAME" 2>/dev/null || echo "Database already exists — skipping creation."

# Initialise tables
echo "Initialising tables..."
cd "$ROOT_DIR"
python -m atlas_research.cli db init

echo "Done. Run 'atlas-research db status' to verify."
