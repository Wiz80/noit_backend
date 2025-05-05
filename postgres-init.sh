#!/bin/bash
set -e

# Script de inicialización para PostgreSQL
echo "Inicializando base de datos PostgreSQL..."

# La imagen de PostgreSQL ejecuta automáticamente scripts en /docker-entrypoint-initdb.d
# Este script se ejecuta después de que la base de datos se ha creado pero antes 
# de que se acepten conexiones externas

# Si necesitamos crear esquemas o tablas adicionales, lo hacemos aquí
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE SCHEMA IF NOT EXISTS public;
  COMMENT ON SCHEMA public IS 'Standard public schema';
EOSQL

echo "PostgreSQL initialization completed" 