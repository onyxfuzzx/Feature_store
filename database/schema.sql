-- PostgreSQL schema for Feature Store & Model Registry
-- Compatible with Supabase (PostgreSQL 15+)

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS feature_store;
CREATE SCHEMA IF NOT EXISTS model_registry;
CREATE SCHEMA IF NOT EXISTS jobs;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- core.users
CREATE TABLE IF NOT EXISTS core.users (
    id          UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    email       VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- core.roles
CREATE TABLE IF NOT EXISTS core.roles (
    id   UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE
);

-- core.user_roles
CREATE TABLE IF NOT EXISTS core.user_roles (
    user_id UUID NOT NULL REFERENCES core.users(id),
    role_id UUID NOT NULL REFERENCES core.roles(id),
    PRIMARY KEY (user_id, role_id)
);

-- core.audit_log
CREATE TABLE IF NOT EXISTS core.audit_log (
    id          UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    actor_id    UUID REFERENCES core.users(id),
    action      VARCHAR(120) NOT NULL,
    entity_type VARCHAR(120) NOT NULL,
    entity_id   VARCHAR(120) NOT NULL,
    payload_json TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- core.api_keys
CREATE TABLE IF NOT EXISTS core.api_keys (
    id         UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES core.users(id),
    name       VARCHAR(120) NOT NULL,
    key_hash   VARCHAR(255) NOT NULL UNIQUE,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- feature_store.feature_group
CREATE TABLE IF NOT EXISTS feature_store.feature_group (
    id          UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    description VARCHAR(500),
    owner_id    UUID REFERENCES core.users(id),
    tags_json   TEXT,
    environment VARCHAR(40) NOT NULL DEFAULT 'dev',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- feature_store.feature_definition
CREATE TABLE IF NOT EXISTS feature_store.feature_definition (
    id                   UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    group_id             UUID NOT NULL REFERENCES feature_store.feature_group(id),
    name                 VARCHAR(120) NOT NULL,
    dtype                VARCHAR(40) NOT NULL,
    description          VARCHAR(500),
    source_sql           TEXT NOT NULL,
    refresh_interval     VARCHAR(40) NOT NULL,
    status               VARCHAR(40) NOT NULL DEFAULT 'draft',
    validation_rules_json TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- feature_store.feature_lineage
CREATE TABLE IF NOT EXISTS feature_store.feature_lineage (
    id                  UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    feature_id          UUID NOT NULL REFERENCES feature_store.feature_definition(id),
    source_table        VARCHAR(200) NOT NULL,
    source_columns_json TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- feature_store.feature_materialization
CREATE TABLE IF NOT EXISTS feature_store.feature_materialization (
    id            UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    feature_id    UUID NOT NULL REFERENCES feature_store.feature_definition(id),
    status        VARCHAR(40) NOT NULL,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    row_count     INTEGER,
    error_message TEXT
);

-- feature_store.feature_values_online
CREATE TABLE IF NOT EXISTS feature_store.feature_values_online (
    entity_key VARCHAR(120) NOT NULL,
    feature_id UUID NOT NULL REFERENCES feature_store.feature_definition(id),
    value      TEXT,
    event_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (entity_key, feature_id)
);

-- feature_store.feature_values_offline
CREATE TABLE IF NOT EXISTS feature_store.feature_values_offline (
    entity_key VARCHAR(120) NOT NULL,
    feature_id UUID NOT NULL REFERENCES feature_store.feature_definition(id),
    event_time TIMESTAMPTZ NOT NULL,
    value      TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (entity_key, feature_id, event_time)
);

-- feature_store.sample_events (seed data source)
CREATE TABLE IF NOT EXISTS feature_store.sample_events (
    customer_id VARCHAR(50) NOT NULL,
    amount      NUMERIC(12, 2) NOT NULL,
    event_time  TIMESTAMPTZ NOT NULL
);

-- model_registry.model
CREATE TABLE IF NOT EXISTS model_registry.model (
    id          UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    description VARCHAR(500),
    owner_id    UUID REFERENCES core.users(id),
    environment VARCHAR(40) NOT NULL DEFAULT 'dev',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- model_registry.model_version
CREATE TABLE IF NOT EXISTS model_registry.model_version (
    id           UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    model_id     UUID NOT NULL REFERENCES model_registry.model(id),
    version      VARCHAR(40) NOT NULL,
    stage        VARCHAR(40) NOT NULL DEFAULT 'Staging',
    metrics_json TEXT,
    params_json  TEXT,
    artifact_uri VARCHAR(500),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- model_registry.model_lineage
CREATE TABLE IF NOT EXISTS model_registry.model_lineage (
    id               UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    model_version_id UUID NOT NULL REFERENCES model_registry.model_version(id),
    feature_ids_json TEXT,
    dataset_uri      VARCHAR(500),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- model_registry.model_stage_history
CREATE TABLE IF NOT EXISTS model_registry.model_stage_history (
    id               UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    model_version_id UUID NOT NULL REFERENCES model_registry.model_version(id),
    from_stage       VARCHAR(40) NOT NULL,
    to_stage         VARCHAR(40) NOT NULL,
    changed_by       UUID REFERENCES core.users(id),
    changed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- jobs.job_definition
CREATE TABLE IF NOT EXISTS jobs.job_definition (
    id           UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    name         VARCHAR(120) NOT NULL,
    type         VARCHAR(60) NOT NULL,
    cron         VARCHAR(60) NOT NULL,
    payload_json TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- jobs.job_run
CREATE TABLE IF NOT EXISTS jobs.job_run (
    id                UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    job_definition_id UUID NOT NULL REFERENCES jobs.job_definition(id),
    status            VARCHAR(40) NOT NULL,
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    log               TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_feature_definition_group ON feature_store.feature_definition (group_id);
CREATE INDEX IF NOT EXISTS idx_feature_values_online_feature ON feature_store.feature_values_online (feature_id);
CREATE INDEX IF NOT EXISTS idx_model_version_model ON model_registry.model_version (model_id);
CREATE INDEX IF NOT EXISTS idx_job_run_job ON jobs.job_run (job_definition_id);
