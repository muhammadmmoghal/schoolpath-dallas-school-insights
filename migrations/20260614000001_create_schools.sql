-- Migration: create public.schools
-- Phase 6 — Supabase schema
-- Source: data/processed/dallas_school_insights.csv (60 rows x 79 cols)
-- Primary key: campus_id (9-digit TEA campus number)
-- Type map:
--   ID / classification text  → text
--   enrollment count / year   → double precision / integer
--   percentages / scores      → double precision (nullable)
--   CRDC / TAPR numerics      → double precision (nullable; masking codes → null)
--   coordinates               → double precision NOT NULL
--   indicator strings         → text (nullable)

CREATE TABLE public.schools (
    -- ── Identity ─────────────────────────────────────────────────────────────
    campus_id                           text         NOT NULL,
    district_id                         text         NOT NULL,
    nces_school_id                      text         NOT NULL,
    school_name                         text         NOT NULL,
    district_name                       text         NOT NULL,

    -- ── Classification ───────────────────────────────────────────────────────
    district_type                       text         NOT NULL,
    instruction_type                    text         NOT NULL,
    charter_type                        text,
    school_level                        text         NOT NULL,
    operator_type                       text         NOT NULL,
    grade_range                         text         NOT NULL,

    -- ── Location and roster ──────────────────────────────────────────────────
    enrollment                          double precision NOT NULL,
    school_status                       text         NOT NULL,
    school_site_city                    text         NOT NULL,
    school_site_address                 text         NOT NULL,
    school_site_zip                     text         NOT NULL,
    magnet_status                       text         NOT NULL,
    enrollment_source_year              integer      NOT NULL,

    -- ── TEA 2025 Accountability ───────────────────────────────────────────────
    accountability_rating_2025          text,
    accountability_status_2025          text,
    accountability_score_2025           double precision,
    acct_grade_type_2025                text,
    acct_grade_span_2025                text,
    acct_grade_low_2025                 text,
    acct_grade_high_2025                text,
    acct_alt_ed_flag_2025               text,
    acct_daep_flag_2025                 text,
    acct_jj_flag_2025                   text,
    acct_alted_flag_2025                text,
    acct_residential_flag_2025          text,

    -- ── TAPR 2025 — Student membership ───────────────────────────────────────
    tapr_membership_all_count_2025      double precision,
    tapr_membership_sped_count_2025     double precision,
    tapr_membership_sped_pct_2025       double precision,
    tapr_enrollment_all_count_2025      double precision,
    tapr_enrollment_sped_count_2025     double precision,
    tapr_enrollment_sped_pct_2025       double precision,

    -- ── TAPR 2024 — Attendance and chronic absence ───────────────────────────
    tapr_att_all_rate_2024              double precision,
    tapr_att_sped_rate_2024             double precision,
    tapr_chronic_abs_all_rate_2024      double precision,
    tapr_chronic_abs_sped_rate_2024     double precision,

    -- ── TAPR 2025 — Staff experience ─────────────────────────────────────────
    tapr_avg_teacher_exp_years_2025     double precision,
    tapr_avg_teacher_tenure_years_2025  double precision,
    tapr_beginning_teacher_fte_pct_2025 double precision,
    tapr_teacher_1to5yr_pct_2025        double precision,
    tapr_teacher_6to10yr_pct_2025       double precision,
    tapr_teacher_11to20yr_pct_2025      double precision,
    tapr_teacher_21to30yr_pct_2025      double precision,
    tapr_teacher_over30yr_pct_2025      double precision,

    -- ── CRDC 2021-22 — Enrollment ────────────────────────────────────────────
    crdc_tot_enr_total_2122             double precision,
    crdc_idea_enr_total_2122            double precision,
    crdc_504_enr_total_2122             double precision,

    -- ── CRDC 2021-22 — Suspensions ───────────────────────────────────────────
    crdc_idea_iss_students_total_2122   double precision,
    crdc_oos_instances_no_dis_2122      double precision,
    crdc_oos_instances_idea_2122        double precision,
    crdc_oos_instances_504_2122         double precision,
    crdc_idea_sing_oos_total_2122       double precision,
    crdc_idea_mult_oos_total_2122       double precision,

    -- ── CRDC 2021-22 — Expulsions ────────────────────────────────────────────
    crdc_idea_exp_with_svc_total_2122   double precision,
    crdc_idea_exp_no_svc_total_2122     double precision,
    crdc_idea_exp_zerotol_total_2122    double precision,

    -- ── CRDC 2021-22 — Restraint and seclusion ───────────────────────────────
    crdc_rs_mech_instances_idea_2122    double precision,
    crdc_rs_phys_instances_idea_2122    double precision,
    crdc_rs_secl_instances_idea_2122    double precision,

    -- ── CRDC 2021-22 — Harassment and bullying ───────────────────────────────
    crdc_hb_dis_allegations_2122        double precision,
    crdc_hb_dis_reported_total_2122     double precision,
    crdc_hb_dis_disciplined_total_2122  double precision,

    -- ── CRDC 2021-22 — Referrals and arrests ─────────────────────────────────
    crdc_idea_ref_law_total_2122        double precision,
    crdc_idea_arr_total_2122            double precision,

    -- ── CRDC 2021-22 — Offenses ──────────────────────────────────────────────
    crdc_offense_assault_with_wpn_2122  double precision,
    crdc_offense_assault_no_wpn_2122    double precision,
    crdc_offense_wpn_possession_2122    double precision,
    crdc_offense_robbery_with_wpn_2122  double precision,
    crdc_offense_robbery_no_wpn_2122    double precision,
    crdc_offense_threat_with_wpn_2122   double precision,
    crdc_offense_threat_no_wpn_2122     double precision,
    crdc_offense_firearm_ind_2122       text,
    crdc_offense_homicide_ind_2122      text,

    -- ── ArcGIS 2024-25 — Coordinates ─────────────────────────────────────────
    latitude                            double precision NOT NULL,
    longitude                           double precision NOT NULL,

    CONSTRAINT schools_pkey PRIMARY KEY (campus_id)
);

COMMENT ON TABLE public.schools IS
    'Dallas public school insights — 60 schools, 79 columns. Source of truth: data/processed/dallas_school_insights.parquet.';
