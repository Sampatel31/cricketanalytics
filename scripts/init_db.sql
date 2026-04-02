-- PostgreSQL initialisation script
-- Run this once as a superuser before starting the application.

-- Create the application database
CREATE DATABASE cricketanalytics
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

-- Create application user (if not already present)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'cricket_app') THEN
        CREATE ROLE cricket_app WITH LOGIN PASSWORD 'change_me_in_production';
    END IF;
END
$$;

-- Grant privileges
GRANT CONNECT ON DATABASE cricketanalytics TO cricket_app;
\c cricketanalytics
GRANT USAGE ON SCHEMA public TO cricket_app;
GRANT CREATE ON SCHEMA public TO cricket_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cricket_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO cricket_app;

-- Enable the pgcrypto extension for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;
