-- Dimensigon Database Initialization Script
-- This script is executed automatically on first PostgreSQL container startup

-- Ensure database encoding is UTF-8
-- This is handled by POSTGRES_INITDB_ARGS in docker-compose.yml

-- Grant all privileges to dimensigon user on public schema
GRANT ALL ON SCHEMA public TO dimensigon;

-- Create extensions if needed (optional)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set default search path
ALTER DATABASE dimensigon SET search_path TO public;

-- Performance tuning settings (optional)
-- These are applied to the database level
-- ALTER DATABASE dimensigon SET log_statement = 'all';
-- ALTER DATABASE dimensigon SET log_duration = on;

-- Table creation is handled automatically by SQLAlchemy
-- Dimensigon will create all necessary tables on first startup

-- Create audit log table (optional, for future use)
-- CREATE TABLE IF NOT EXISTS audit_log (
--     id SERIAL PRIMARY KEY,
--     timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
--     user_id UUID,
--     action VARCHAR(50) NOT NULL,
--     entity_type VARCHAR(50),
--     entity_id UUID,
--     details JSONB,
--     ip_address INET
-- );

-- Create index for faster queries (optional)
-- CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
-- CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);

-- Grant privileges on audit log
-- GRANT ALL ON audit_log TO dimensigon;
-- GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO dimensigon;

COMMIT;
