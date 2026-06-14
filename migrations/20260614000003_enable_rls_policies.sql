-- Migration: enable RLS and create read-only policies
-- Phase 6 — security configuration
--
-- schools:
--   anon + authenticated → SELECT only
--   no public INSERT / UPDATE / DELETE
--
-- pipeline_runs:
--   RLS enabled; no public policies (service role only)

-- ── public.schools ────────────────────────────────────────────────────────────

ALTER TABLE public.schools ENABLE ROW LEVEL SECURITY;

CREATE POLICY "schools_anon_select"
    ON public.schools
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "schools_authenticated_select"
    ON public.schools
    FOR SELECT
    TO authenticated
    USING (true);

-- ── public.pipeline_runs ──────────────────────────────────────────────────────

ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;
-- No SELECT/INSERT/UPDATE/DELETE policies for anon or authenticated.
-- The service_role key bypasses RLS and can read/write pipeline_runs.
