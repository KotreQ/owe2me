#!/bin/sh
set -eu

# Compose does not run migrations on its own; a fresh database has no tables at all.
# Set RUN_MIGRATIONS=false to skip (e.g. when a release step already ran them).
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "applying database migrations"
    alembic upgrade head
fi

exec "$@"
