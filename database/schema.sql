IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'core')
    EXEC('CREATE SCHEMA core');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'feature_store')
    EXEC('CREATE SCHEMA feature_store');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'model_registry')
    EXEC('CREATE SCHEMA model_registry');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'jobs')
    EXEC('CREATE SCHEMA jobs');
GO

IF OBJECT_ID('core.users', 'U') IS NULL
CREATE TABLE core.users (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    name NVARCHAR(120) NOT NULL,
    email NVARCHAR(200) NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID('core.roles', 'U') IS NULL
CREATE TABLE core.roles (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    name NVARCHAR(80) NOT NULL UNIQUE
);
GO

IF OBJECT_ID('core.user_roles', 'U') IS NULL
CREATE TABLE core.user_roles (
    user_id UNIQUEIDENTIFIER NOT NULL,
    role_id UNIQUEIDENTIFIER NOT NULL,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES core.users(id),
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES core.roles(id)
);
GO

IF OBJECT_ID('core.audit_log', 'U') IS NULL
CREATE TABLE core.audit_log (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    actor_id UNIQUEIDENTIFIER NULL,
    action NVARCHAR(120) NOT NULL,
    entity_type NVARCHAR(120) NOT NULL,
    entity_id NVARCHAR(120) NOT NULL,
    payload_json NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_audit_log_actor FOREIGN KEY (actor_id) REFERENCES core.users(id)
);
GO

IF OBJECT_ID('feature_store.feature_group', 'U') IS NULL
CREATE TABLE feature_store.feature_group (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    name NVARCHAR(120) NOT NULL,
    description NVARCHAR(500) NULL,
    owner_id UNIQUEIDENTIFIER NULL,
    tags_json NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_feature_group_owner FOREIGN KEY (owner_id) REFERENCES core.users(id)
);
GO

IF OBJECT_ID('feature_store.feature_definition', 'U') IS NULL
CREATE TABLE feature_store.feature_definition (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    group_id UNIQUEIDENTIFIER NOT NULL,
    name NVARCHAR(120) NOT NULL,
    dtype NVARCHAR(40) NOT NULL,
    description NVARCHAR(500) NULL,
    source_sql NVARCHAR(MAX) NOT NULL,
    refresh_interval NVARCHAR(40) NOT NULL,
    status NVARCHAR(40) NOT NULL DEFAULT 'draft',
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_feature_definition_group FOREIGN KEY (group_id) REFERENCES feature_store.feature_group(id)
);
GO

IF OBJECT_ID('feature_store.feature_lineage', 'U') IS NULL
CREATE TABLE feature_store.feature_lineage (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    feature_id UNIQUEIDENTIFIER NOT NULL,
    source_table NVARCHAR(200) NOT NULL,
    source_columns_json NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_feature_lineage_feature FOREIGN KEY (feature_id) REFERENCES feature_store.feature_definition(id)
);
GO

IF OBJECT_ID('feature_store.feature_materialization', 'U') IS NULL
CREATE TABLE feature_store.feature_materialization (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    feature_id UNIQUEIDENTIFIER NOT NULL,
    status NVARCHAR(40) NOT NULL,
    started_at DATETIME2 NULL,
    finished_at DATETIME2 NULL,
    row_count INT NULL,
    error_message NVARCHAR(MAX) NULL,
    CONSTRAINT fk_feature_materialization_feature FOREIGN KEY (feature_id) REFERENCES feature_store.feature_definition(id)
);
GO

IF OBJECT_ID('feature_store.feature_values_online', 'U') IS NULL
CREATE TABLE feature_store.feature_values_online (
    entity_key NVARCHAR(120) NOT NULL,
    feature_id UNIQUEIDENTIFIER NOT NULL,
    value NVARCHAR(MAX) NULL,
    event_time DATETIME2 NULL,
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    PRIMARY KEY (entity_key, feature_id),
    CONSTRAINT fk_feature_values_online_feature FOREIGN KEY (feature_id) REFERENCES feature_store.feature_definition(id)
);
GO

IF OBJECT_ID('feature_store.feature_values_offline', 'U') IS NULL
CREATE TABLE feature_store.feature_values_offline (
    entity_key NVARCHAR(120) NOT NULL,
    feature_id UNIQUEIDENTIFIER NOT NULL,
    value NVARCHAR(MAX) NULL,
    event_time DATETIME2 NOT NULL,
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    PRIMARY KEY (entity_key, feature_id, event_time),
    CONSTRAINT fk_feature_values_offline_feature FOREIGN KEY (feature_id) REFERENCES feature_store.feature_definition(id)
);
GO

IF OBJECT_ID('model_registry.model', 'U') IS NULL
CREATE TABLE model_registry.model (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    name NVARCHAR(120) NOT NULL,
    description NVARCHAR(500) NULL,
    owner_id UNIQUEIDENTIFIER NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_model_owner FOREIGN KEY (owner_id) REFERENCES core.users(id)
);
GO

IF OBJECT_ID('model_registry.model_version', 'U') IS NULL
CREATE TABLE model_registry.model_version (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    model_id UNIQUEIDENTIFIER NOT NULL,
    version NVARCHAR(40) NOT NULL,
    stage NVARCHAR(40) NOT NULL DEFAULT 'Staging',
    metrics_json NVARCHAR(MAX) NULL,
    params_json NVARCHAR(MAX) NULL,
    artifact_uri NVARCHAR(500) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_model_version_model FOREIGN KEY (model_id) REFERENCES model_registry.model(id)
);
GO

IF OBJECT_ID('model_registry.model_lineage', 'U') IS NULL
CREATE TABLE model_registry.model_lineage (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    model_version_id UNIQUEIDENTIFIER NOT NULL,
    feature_ids_json NVARCHAR(MAX) NULL,
    dataset_uri NVARCHAR(500) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_model_lineage_version FOREIGN KEY (model_version_id) REFERENCES model_registry.model_version(id)
);
GO

IF OBJECT_ID('model_registry.model_stage_history', 'U') IS NULL
CREATE TABLE model_registry.model_stage_history (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    model_version_id UNIQUEIDENTIFIER NOT NULL,
    from_stage NVARCHAR(40) NOT NULL,
    to_stage NVARCHAR(40) NOT NULL,
    changed_by UNIQUEIDENTIFIER NULL,
    changed_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT fk_model_stage_history_version FOREIGN KEY (model_version_id) REFERENCES model_registry.model_version(id),
    CONSTRAINT fk_model_stage_history_user FOREIGN KEY (changed_by) REFERENCES core.users(id)
);
GO

IF OBJECT_ID('jobs.job_definition', 'U') IS NULL
CREATE TABLE jobs.job_definition (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    name NVARCHAR(120) NOT NULL,
    type NVARCHAR(60) NOT NULL,
    cron NVARCHAR(60) NOT NULL,
    payload_json NVARCHAR(MAX) NULL,
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID('jobs.job_run', 'U') IS NULL
CREATE TABLE jobs.job_run (
    id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
    job_definition_id UNIQUEIDENTIFIER NOT NULL,
    status NVARCHAR(40) NOT NULL,
    started_at DATETIME2 NULL,
    finished_at DATETIME2 NULL,
    log NVARCHAR(MAX) NULL,
    CONSTRAINT fk_job_run_job FOREIGN KEY (job_definition_id) REFERENCES jobs.job_definition(id)
);
GO

CREATE INDEX idx_feature_definition_group ON feature_store.feature_definition (group_id);
CREATE INDEX idx_feature_values_online_feature ON feature_store.feature_values_online (feature_id);
CREATE INDEX idx_model_version_model ON model_registry.model_version (model_id);
CREATE INDEX idx_job_run_job ON jobs.job_run (job_definition_id);
GO
