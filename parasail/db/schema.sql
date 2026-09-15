-- ParaSail schema - PostgreSQL 16 + PostGIS 3.4
-- Phase 2 artefact: relational + geospatial state for the advisory pipeline.

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------- species --
CREATE TABLE IF NOT EXISTS species_registry (
    scientific_name TEXT PRIMARY KEY,
    common_name     TEXT NOT NULL,
    worms_aphia_id  INTEGER UNIQUE,
    modelling_path  TEXT NOT NULL CHECK (modelling_path IN
                      ('blended', 'habitat_led', 'habitat_fallback')),
    data_availability DOUBLE PRECISION NOT NULL DEFAULT 0.5
                    CHECK (data_availability BETWEEN 0 AND 1),
    active          BOOLEAN NOT NULL DEFAULT TRUE
);

-- ------------------------------------------------------------ regulations --
-- Geometry is Geometry (not Polygon): marine protected areas arrive as
-- MultiPolygons (island groups, e.g. Gulf of Mannar Marine NP). Attribute
-- columns beyond name/authority feed the dashboard popups and analysis.
-- Build/refresh the registry with scripts/fetch_mpas.py + load_mpas.py.
CREATE TABLE IF NOT EXISTS mpa_polygons (
    mpa_id    SERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    authority TEXT,
    desig     TEXT,                           -- National Park, Sanctuary, Ramsar ...
    iucn_cat  TEXT,
    no_take   TEXT,
    source    TEXT,                           -- wdpa | osm
    geometry  geometry(Geometry, 4326) NOT NULL,
    valid_from DATE,
    valid_to   DATE
);
CREATE INDEX IF NOT EXISTS mpa_geom_idx ON mpa_polygons USING GIST (geometry);

CREATE TABLE IF NOT EXISTS closure_calendar (
    closure_id  SERIAL PRIMARY KEY,
    species     TEXT REFERENCES species_registry (scientific_name),
    months      INTEGER[] NOT NULL,           -- e.g. {6,7} for June-July
    reason      TEXT NOT NULL,
    citation    TEXT NOT NULL
);

-- ------------------------------------------------- environmental grid data --
CREATE TABLE IF NOT EXISTS environmental_fields (
    field_id    BIGSERIAL PRIMARY KEY,
    variable    TEXT NOT NULL,                -- sst, chlorophyll_a, wind_u, ...
    source      TEXT NOT NULL,                -- open-meteo, copernicus, erddap
    ts          TIMESTAMPTZ NOT NULL,
    geom        geometry(Point, 4326) NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS env_lookup_idx
    ON environmental_fields (variable, ts);
CREATE INDEX IF NOT EXISTS env_geom_idx
    ON environmental_fields USING GIST (geom);

CREATE TABLE IF NOT EXISTS occurrences (
    occurrence_id BIGSERIAL PRIMARY KEY,
    species       TEXT REFERENCES species_registry (scientific_name),
    dataset       TEXT NOT NULL,              -- gbif, obis, custom_upload
    ts            TIMESTAMPTZ,
    geom          geometry(Point, 4326) NOT NULL,
    depth_m       DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS occ_geom_idx ON occurrences USING GIST (geom);
CREATE INDEX IF NOT EXISTS occ_species_ts_idx ON occurrences (species, ts);

-- ------------------------------------------------------------- model runs --
CREATE TABLE IF NOT EXISTS model_registry (
    model_id   SERIAL PRIMARY KEY,
    task       TEXT NOT NULL,                 -- detection, classification, ...
    checkpoint TEXT NOT NULL,
    trained_at TIMESTAMPTZ DEFAULT now(),
    metrics    JSONB
);

-- -------------------------------------------------------------- advisories --
-- Full audit trail: every recommendation ever issued, with its inputs.
CREATE TABLE IF NOT EXISTS advisories (
    advisory_id BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    request     JSONB NOT NULL,               -- lat, lon, species, window
    allowed     BOOLEAN NOT NULL,
    score       DOUBLE PRECISION,             -- NULL when hard-blocked
    class       TEXT NOT NULL CHECK (class IN
                 ('PROCEED', 'PROCEED WITH CAUTION',
                  'DELAY OR RELOCATE', 'DO NOT FISH')),
    block_reason TEXT,
    components  JSONB,                        -- C, W, B and data ages
    context     JSONB                         -- retrieved citations
);
