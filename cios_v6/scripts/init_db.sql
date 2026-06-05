-- CIOS Database Initialization
-- Run once on first startup

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for fuzzy search

-- Optimize for time-series vital sign queries
-- (TimescaleDB would be used in production for hypertables)

-- Full-text search index on patient names
-- (created after tables exist via alembic)

-- Set timezone
SET timezone = 'UTC';

-- Performance settings for CIOS workload
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
