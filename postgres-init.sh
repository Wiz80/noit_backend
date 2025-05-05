#!/bin/bash

# Este script prepara el directorio de datos de PostgreSQL
if [ -d /var/lib/postgresql/data ] && [ "$(ls -A /var/lib/postgresql/data)" ]; then
  echo "El directorio de datos ya existe, estableciendo permisos correctos"
  chmod -R 700 /var/lib/postgresql/data
  chown -R postgres:postgres /var/lib/postgresql/data
else
  echo "Creando directorio de datos vacío"
  mkdir -p /var/lib/postgresql/data
  chmod 700 /var/lib/postgresql/data
  chown postgres:postgres /var/lib/postgresql/data
fi

# Iniciar PostgreSQL
exec docker-entrypoint.sh postgres 