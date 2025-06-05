#!/bin/bash
set -e

# This script will be executed by the postgres container on startup if the database needs initialization.
# It uses the POSTGRES_USER and POSTGRES_DB environment variables, which are set in docker-compose.yml
# for the postgres service and sourced from your .env file.

echo "Attempting to create schema 'kestra_schema' owned by user '${POSTGRES_USER}' in database '${POSTGRES_DB}'..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE SCHEMA IF NOT EXISTS kestra_schema AUTHORIZATION "$POSTGRES_USER";
    GRANT ALL ON SCHEMA kestra_schema TO "$POSTGRES_USER";
    GRANT ALL ON ALL TABLES IN SCHEMA kestra_schema TO "$POSTGRES_USER";
    GRANT ALL ON ALL SEQUENCES IN SCHEMA kestra_schema TO "$POSTGRES_USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA kestra_schema GRANT ALL ON TABLES TO "$POSTGRES_USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA kestra_schema GRANT ALL ON SEQUENCES TO "$POSTGRES_USER";
    COMMENT ON SCHEMA kestra_schema IS 'Schema dedicated for Kestra application data, owned by ${POSTGRES_USER}.';
EOSQL

echo "Schema 'kestra_schema' creation attempt finished." 