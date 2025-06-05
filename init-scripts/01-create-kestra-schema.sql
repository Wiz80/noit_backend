-- Create Kestra schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS kestra_schema;

-- Grant all privileges on the schema to the PostgreSQL user
GRANT ALL ON SCHEMA kestra_schema TO "${POSTGRES_USER}";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA kestra_schema TO "${POSTGRES_USER}";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kestra_schema TO "${POSTGRES_USER}";

-- Set default privileges for future tables and sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA kestra_schema GRANT ALL ON TABLES TO "${POSTGRES_USER}";
ALTER DEFAULT PRIVILEGES IN SCHEMA kestra_schema GRANT ALL ON SEQUENCES TO "${POSTGRES_USER}"; 