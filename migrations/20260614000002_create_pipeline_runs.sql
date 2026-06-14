-- Migration: create public.pipeline_runs
-- Phase 6 — load-run audit trail

CREATE TABLE public.pipeline_runs (
    id          bigserial    PRIMARY KEY,
    loaded_at   timestamptz  NOT NULL DEFAULT now(),
    source_file text         NOT NULL,
    row_count   integer      NOT NULL,
    notes       text
);

COMMENT ON TABLE public.pipeline_runs IS
    'One row per execution of scripts/load_supabase.py. Not exposed to public.';
