-- =====================================================================
-- FOOTBALL TALENT AI — Esquema de Base de Datos (PostgreSQL)
-- =====================================================================
-- Diseñado para v1 del MVP, usando datos ingeridos periódicamente
-- desde Sofascore (no en tiempo real — ver arquitectura de ingesta).
--
-- Principios de diseño:
--   1. Las stats crudas se guardan en JSONB (flexibles, fuente-agnósticas).
--   2. El historial (mensual y de temporada) son snapshots inmutables,
--      nunca se sobreescriben — así se construye la "evolución".
--   3. Las fórmulas de atributos por posición viven en tablas de
--      configuración, no hardcodeadas en el backend.
--   4. Todo dato calculado (atributos, media, DNA, similitud) referencia
--      siempre de qué fuente y con qué versión de fórmula se generó,
--      para poder auditar y recalcular si cambia el modelo.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- para búsqueda de texto en nombres

-- =====================================================================
-- 1. CATÁLOGO: FUENTES DE DATOS
-- =====================================================================
-- Permite que mañana convivan Sofascore + StatsBomb + lo que sea,
-- y saber siempre de dónde viene cada dato.

CREATE TABLE data_sources (
    id              SMALLSERIAL PRIMARY KEY,
    code            VARCHAR(30) UNIQUE NOT NULL,   -- 'sofascore', 'statsbomb', 'manual'
    name            VARCHAR(100) NOT NULL,
    is_commercial_ok BOOLEAN NOT NULL DEFAULT FALSE, -- licencia apta para uso comercial
    notes           TEXT
);

INSERT INTO data_sources (code, name, is_commercial_ok, notes) VALUES
    ('sofascore', 'Sofascore (API interna, scraping)', FALSE,
     'Sin licencia oficial. Uso en v1 para validación/MVP. Migrar antes de monetizar.');

-- =====================================================================
-- 2. EQUIPOS Y COMPETICIONES
-- =====================================================================

CREATE TABLE teams (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id           SMALLINT NOT NULL REFERENCES data_sources(id),
    external_id         VARCHAR(50) NOT NULL,   -- id del equipo en Sofascore
    name                VARCHAR(150) NOT NULL,
    short_name          VARCHAR(50),
    country             VARCHAR(80),
    logo_url            TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, external_id)
);

CREATE TABLE competitions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id           SMALLINT NOT NULL REFERENCES data_sources(id),
    external_id         VARCHAR(50) NOT NULL,   -- unique-tournament id en Sofascore
    name                VARCHAR(150) NOT NULL,  -- "LaLiga", "Premier League"...
    country             VARCHAR(80),
    tier                SMALLINT,               -- 1 = primera división, etc.
    gender              VARCHAR(10) DEFAULT 'male',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, external_id)
);

CREATE TABLE seasons (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    competition_id      UUID NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    source_id           SMALLINT NOT NULL REFERENCES data_sources(id),
    external_id         VARCHAR(50) NOT NULL,   -- season id en Sofascore
    name                VARCHAR(50) NOT NULL,   -- "2025/2026"
    start_date          DATE,
    end_date            DATE,
    is_current          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (competition_id, external_id)
);

CREATE INDEX idx_seasons_current ON seasons (competition_id) WHERE is_current = TRUE;

-- =====================================================================
-- 3. JUGADORES
-- =====================================================================

CREATE TYPE player_position AS ENUM (
    'GK',           -- Portero
    'CB', 'LB', 'RB', 'LWB', 'RWB',                 -- Defensas
    'CDM', 'CM', 'CAM', 'LM', 'RM',                 -- Centrocampistas
    'LW', 'RW', 'CF', 'ST'                          -- Delanteros/Extremos
);

CREATE TABLE players (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id           SMALLINT NOT NULL REFERENCES data_sources(id),
    external_id         VARCHAR(50) NOT NULL,       -- player id en Sofascore
    full_name           VARCHAR(150) NOT NULL,
    display_name        VARCHAR(100) NOT NULL,
    date_of_birth       DATE,
    nationality         VARCHAR(80),
    primary_position    player_position NOT NULL,
    secondary_positions player_position[],           -- posiciones alternativas
    height_cm           SMALLINT,
    preferred_foot      VARCHAR(10),
    current_team_id     UUID REFERENCES teams(id),
    photo_url           TEXT,                        -- sujeto a licencia (sección 16)
    photo_license_ok    BOOLEAN NOT NULL DEFAULT FALSE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, external_id)
);

CREATE INDEX idx_players_name_trgm ON players USING gin (display_name gin_trgm_ops);
CREATE INDEX idx_players_team ON players (current_team_id);
CREATE INDEX idx_players_position ON players (primary_position);

-- Historial de equipos (para no perder el rastro en traspasos/cesiones)
CREATE TABLE player_team_history (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id           UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    team_id             UUID NOT NULL REFERENCES teams(id),
    season_id           UUID NOT NULL REFERENCES seasons(id),
    joined_date         DATE,
    left_date           DATE,
    on_loan             BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_pth_player_season ON player_team_history (player_id, season_id);

-- =====================================================================
-- 4. ESTADÍSTICAS CRUDAS (ingeridas periódicamente)
-- =====================================================================
-- Una fila = las stats de un jugador en una competición/temporada,
-- en el momento en que se hizo la ingesta. Se guarda snapshot mensual,
-- no se sobreescribe (permite reconstruir la evolución real).

CREATE TABLE player_stats_snapshot (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id           UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    season_id           UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    team_id             UUID REFERENCES teams(id),
    source_id           SMALLINT NOT NULL REFERENCES data_sources(id),

    snapshot_date        DATE NOT NULL,             -- fecha de la ingesta (ej. 1º de cada mes)
    accumulation_type     VARCHAR(20) NOT NULL DEFAULT 'total', -- 'total' | 'per90' | 'perMatch'

    -- Stats crudas tal cual llegan de la fuente (goals, expectedGoals,
    -- accuratePasses, successfulDribbles, tackles, rating, etc.)
    raw_stats            JSONB NOT NULL,

    matches_played       SMALLINT,
    minutes_played        INTEGER,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (player_id, season_id, source_id, snapshot_date, accumulation_type)
);

CREATE INDEX idx_stats_snapshot_player ON player_stats_snapshot (player_id, snapshot_date DESC);
CREATE INDEX idx_stats_snapshot_season ON player_stats_snapshot (season_id);
CREATE INDEX idx_stats_snapshot_raw_gin ON player_stats_snapshot USING gin (raw_stats);

-- =====================================================================
-- 5. FÓRMULAS DE ATRIBUTOS POR POSICIÓN (configurables, no hardcodeadas)
-- =====================================================================

CREATE TABLE attributes_catalog (
    id                  SMALLSERIAL PRIMARY KEY,
    code                VARCHAR(30) UNIQUE NOT NULL,  -- 'ritmo','tiro','pase','regate','defensa','fisico'
    display_name        VARCHAR(50) NOT NULL,
    emoji               VARCHAR(10)
);

INSERT INTO attributes_catalog (code, display_name, emoji) VALUES
    ('ritmo',   'Ritmo',    '⚡'),
    ('tiro',    'Tiro',     '🎯'),
    ('pase',    'Pase',     '🎨'),
    ('regate',  'Regate',   '🕺'),
    ('defensa', 'Defensa',  '🛡️'),
    ('fisico',  'Físico',   '💪');

-- Qué peso tiene cada stat cruda (campo del JSONB raw_stats) en el
-- cálculo de cada atributo, para cada posición. version permite
-- iterar el modelo sin perder el histórico de qué fórmula se usó.
CREATE TABLE position_attribute_weights (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position            player_position NOT NULL,
    attribute_id         SMALLINT NOT NULL REFERENCES attributes_catalog(id),
    stat_field           VARCHAR(60) NOT NULL,     -- clave dentro de raw_stats, ej. 'accuratePassesPercentage'
    weight               NUMERIC(5,3) NOT NULL,     -- peso relativo dentro del atributo
    formula_version      SMALLINT NOT NULL DEFAULT 1,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (position, attribute_id, stat_field, formula_version)
);

-- La media general también depende de la posición (sección 4 del doc)
CREATE TABLE position_overall_weights (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position            player_position NOT NULL,
    attribute_id         SMALLINT NOT NULL REFERENCES attributes_catalog(id),
    weight               NUMERIC(5,3) NOT NULL,
    formula_version      SMALLINT NOT NULL DEFAULT 1,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (position, attribute_id, formula_version)
);

-- =====================================================================
-- 6. MEDIA DINÁMICA Y ATRIBUTOS — HISTORIAL MENSUAL (snapshots inmutables)
-- =====================================================================
-- Sección 5 y 6 del doc: la media y cada atributo cambian mes a mes.
-- Nunca se hace UPDATE aquí — cada mes se inserta una fila nueva.

CREATE TABLE player_monthly_rating (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id           UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    season_id           UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    period_year          SMALLINT NOT NULL,
    period_month          SMALLINT NOT NULL CHECK (period_month BETWEEN 1 AND 12),

    overall_rating        NUMERIC(5,2) NOT NULL CHECK (overall_rating BETWEEN 0 AND 100),
    formula_version        SMALLINT NOT NULL DEFAULT 1,

    -- snapshot de las stats crudas usadas para este cálculo (auditoría)
    based_on_snapshot_id   UUID REFERENCES player_stats_snapshot(id),

    matches_played_period   SMALLINT,
    minutes_played_period   INTEGER,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (player_id, season_id, period_year, period_month, formula_version)
);

CREATE INDEX idx_monthly_rating_player_period
    ON player_monthly_rating (player_id, period_year, period_month);

-- Atributos individuales del snapshot mensual (Ritmo, Tiro, Pase...)
CREATE TABLE player_monthly_attribute (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    monthly_rating_id     UUID NOT NULL REFERENCES player_monthly_rating(id) ON DELETE CASCADE,
    attribute_id           SMALLINT NOT NULL REFERENCES attributes_catalog(id),
    value                 NUMERIC(5,2) NOT NULL CHECK (value BETWEEN 0 AND 100),
    UNIQUE (monthly_rating_id, attribute_id)
);

CREATE INDEX idx_monthly_attribute_rating ON player_monthly_attribute (monthly_rating_id);

-- =====================================================================
-- 7. RESUMEN DE TEMPORADA (Season Card — sección 7 y 8 del doc)
-- =====================================================================
-- Se calcula al cierre de temporada a partir de player_monthly_rating.

CREATE TABLE player_season_summary (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id           UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    season_id           UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,

    initial_rating        NUMERIC(5,2),
    final_rating           NUMERIC(5,2),
    best_rating            NUMERIC(5,2),
    best_rating_month       DATE,
    worst_rating            NUMERIC(5,2),
    worst_rating_month       DATE,
    season_average          NUMERIC(5,2),
    evolution                NUMERIC(5,2),   -- final - initial

    total_matches            SMALLINT,
    total_minutes             INTEGER,

    formula_version           SMALLINT NOT NULL DEFAULT 1,
    computed_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (player_id, season_id, formula_version)
);

-- =====================================================================
-- 8. PLAYER DNA (sección 9 del doc)
-- =====================================================================

CREATE TABLE dna_components_catalog (
    id                  SMALLSERIAL PRIMARY KEY,
    code                VARCHAR(30) UNIQUE NOT NULL,  -- 'creatividad','progresion','velocidad'...
    display_name        VARCHAR(50) NOT NULL
);

INSERT INTO dna_components_catalog (code, display_name) VALUES
    ('creatividad', 'Creatividad'),
    ('progresion',  'Progresión'),
    ('verticalidad','Verticalidad'),
    ('decisiones',  'Toma de decisiones'),
    ('intensidad',  'Intensidad'),
    ('finalizacion','Finalización'),
    ('defensa',     'Juego defensivo'),
    ('velocidad',   'Velocidad'),
    ('conduccion',  'Conducción');

CREATE TABLE player_dna_snapshot (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id           UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    season_id           UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    snapshot_date         DATE NOT NULL,
    formula_version        SMALLINT NOT NULL DEFAULT 1,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (player_id, season_id, snapshot_date, formula_version)
);

CREATE TABLE player_dna_value (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dna_snapshot_id       UUID NOT NULL REFERENCES player_dna_snapshot(id) ON DELETE CASCADE,
    component_id           SMALLINT NOT NULL REFERENCES dna_components_catalog(id),
    value                  NUMERIC(5,2) NOT NULL CHECK (value BETWEEN 0 AND 100),
    UNIQUE (dna_snapshot_id, component_id)
);

-- Vector normalizado del perfil del jugador, listo para similitud (sección 10)
CREATE TABLE player_profile_vector (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id           UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    season_id           UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    dna_snapshot_id       UUID REFERENCES player_dna_snapshot(id),
    vector                 NUMERIC[] NOT NULL,   -- features normalizadas, orden fijo documentado en backend
    formula_version         SMALLINT NOT NULL DEFAULT 1,
    computed_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (player_id, season_id, formula_version)
);

-- =====================================================================
-- 9. SIMILITUD ENTRE JUGADORES (sección 10 — cacheada, no siempre on-the-fly)
-- =====================================================================

CREATE TABLE player_similarity (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id            UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    similar_player_id      UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    similarity_score        NUMERIC(5,2) NOT NULL CHECK (similarity_score BETWEEN 0 AND 100),
    main_reasons             TEXT[],   -- ["progresión con balón", "creación de ocasiones"]
    formula_version           SMALLINT NOT NULL DEFAULT 1,
    computed_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (player_id <> similar_player_id),
    UNIQUE (player_id, similar_player_id, formula_version)
);

CREATE INDEX idx_similarity_player_score
    ON player_similarity (player_id, similarity_score DESC);

-- =====================================================================
-- 10. HIDDEN GEMS (sección 12)
-- =====================================================================

CREATE TABLE player_hidden_gem_flag (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id           UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    season_id           UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    performance_score      NUMERIC(5,2),
    estimated_potential      NUMERIC(5,2),
    recognition_level         VARCHAR(20),   -- 'bajo' | 'medio' | 'alto'
    explanation                TEXT,          -- generado por IA, basado en datos
    formula_version             SMALLINT NOT NULL DEFAULT 1,
    computed_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (player_id, season_id, formula_version)
);

-- =====================================================================
-- 11. EXPLICACIONES DE IA GENERATIVA (auditoría de lo que genera el LLM)
-- =====================================================================
-- Guardamos qué se le mostró al usuario y a partir de qué datos,
-- para poder revisar que la IA "no inventa" (sección 15 del doc).

CREATE TABLE ai_explanation (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id            UUID REFERENCES players(id) ON DELETE CASCADE,
    explanation_type       VARCHAR(30) NOT NULL,  -- 'player_analysis' | 'similarity' | 'hidden_gem' | 'search_result'
    prompt_context           JSONB NOT NULL,        -- datos reales pasados al LLM
    generated_text            TEXT NOT NULL,
    model_used                 VARCHAR(60),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_explanation_player ON ai_explanation (player_id, created_at DESC);

-- =====================================================================
-- 12. LOG DE INGESTA (para saber qué se actualizó y cuándo)
-- =====================================================================

CREATE TABLE ingestion_log (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id            SMALLINT NOT NULL REFERENCES data_sources(id),
    job_type               VARCHAR(40) NOT NULL,  -- 'monthly_stats_refresh', 'season_close', etc.
    started_at              TIMESTAMPTZ NOT NULL,
    finished_at              TIMESTAMPTZ,
    status                    VARCHAR(20) NOT NULL DEFAULT 'running', -- 'running'|'success'|'failed'
    records_processed         INTEGER DEFAULT 0,
    error_message              TEXT
);

-- =====================================================================
-- FIN DEL ESQUEMA v1
-- =====================================================================
