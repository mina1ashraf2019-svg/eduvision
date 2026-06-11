-- ============================================================
-- EduVision LMS v3.0 — Full Supabase Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- EXTENSIONS
-- ─────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────
-- 1. PROFILES (extends auth.users)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name   TEXT NOT NULL DEFAULT '',
    avatar_url  TEXT,
    bio         TEXT,
    language    TEXT NOT NULL DEFAULT 'ar' CHECK (language IN ('ar','en')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email)
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ─────────────────────────────────────────────────────────────
-- 2. RBAC — ROLES & PERMISSIONS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS public.role_permissions (
    role_id       UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES public.permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS public.user_roles (
    user_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    role_id    UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
    granted_by UUID REFERENCES public.profiles(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

-- ── Seed Permissions ──
INSERT INTO public.permissions (name, description) VALUES
    ('manage_users',        'Create, edit, delete users'),
    ('manage_subjects',     'Create, edit, delete subjects'),
    ('manage_teachers',     'Assign teachers to subjects'),
    ('manage_lectures',     'Create, edit, delete lectures'),
    ('manage_sections',     'Add, reorder, configure lecture sections'),
    ('manage_exams',        'Create and edit exams'),
    ('manage_access_codes', 'Generate and manage access code batches'),
    ('view_reports',        'View student results and analytics'),
    ('grade_homework',      'Grade uploaded homework submissions'),
    ('manage_discussions',  'Moderate discussion sections'),
    ('view_audit_log',      'View system audit log'),
    ('manage_roles',        'Assign roles to users')
ON CONFLICT (name) DO NOTHING;

-- ── Seed Roles ──
INSERT INTO public.roles (name, description) VALUES
    ('admin',      'Full system access'),
    ('co_admin',   'Administrative access except role management'),
    ('teacher',    'Manage own subjects and lectures'),
    ('student',    'Access enrolled subjects')
ON CONFLICT (name) DO NOTHING;

-- ── Assign permissions to roles ──
DO $$
DECLARE
    r_admin     UUID := (SELECT id FROM public.roles WHERE name = 'admin');
    r_co_admin  UUID := (SELECT id FROM public.roles WHERE name = 'co_admin');
    r_teacher   UUID := (SELECT id FROM public.roles WHERE name = 'teacher');
BEGIN
    -- Admin: all permissions
    INSERT INTO public.role_permissions (role_id, permission_id)
    SELECT r_admin, id FROM public.permissions
    ON CONFLICT DO NOTHING;

    -- Co-Admin: all except manage_roles
    INSERT INTO public.role_permissions (role_id, permission_id)
    SELECT r_co_admin, id FROM public.permissions
    WHERE name != 'manage_roles'
    ON CONFLICT DO NOTHING;

    -- Teacher: manage own lectures/sections/exams, view reports, grade, discussions
    INSERT INTO public.role_permissions (role_id, permission_id)
    SELECT r_teacher, id FROM public.permissions
    WHERE name IN ('manage_lectures','manage_sections','manage_exams',
                   'view_reports','grade_homework','manage_discussions')
    ON CONFLICT DO NOTHING;
END;
$$;

-- ── Permission helper functions ──
CREATE OR REPLACE FUNCTION public.get_my_permissions()
RETURNS TEXT[] LANGUAGE sql SECURITY DEFINER STABLE AS $$
    SELECT ARRAY_AGG(p.name)
    FROM public.user_roles ur
    JOIN public.role_permissions rp ON ur.role_id = rp.role_id
    JOIN public.permissions p ON rp.permission_id = p.id
    WHERE ur.user_id = auth.uid();
$$;

CREATE OR REPLACE FUNCTION public.has_permission(perm TEXT)
RETURNS BOOLEAN LANGUAGE sql SECURITY DEFINER STABLE AS $$
    SELECT COALESCE(perm = ANY(public.get_my_permissions()), false);
$$;

CREATE OR REPLACE FUNCTION public.get_my_role()
RETURNS TEXT LANGUAGE sql SECURITY DEFINER STABLE AS $$
    SELECT r.name FROM public.user_roles ur
    JOIN public.roles r ON ur.role_id = r.id
    WHERE ur.user_id = auth.uid()
    ORDER BY CASE r.name
        WHEN 'admin'    THEN 1
        WHEN 'co_admin' THEN 2
        WHEN 'teacher'  THEN 3
        ELSE 4
    END LIMIT 1;
$$;

-- ─────────────────────────────────────────────────────────────
-- 3. ACADEMIC STRUCTURE
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.grades (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name_ar  TEXT NOT NULL,
    name_en  TEXT NOT NULL,
    order_num INTEGER DEFAULT 0
);

-- Seed grades
INSERT INTO public.grades (name_ar, name_en, order_num) VALUES
    ('الصف الأول الثانوي',  'Grade 10', 1),
    ('الصف الثاني الثانوي', 'Grade 11', 2),
    ('الصف الثالث الثانوي', 'Grade 12', 3),
    ('الصف الأول الإعدادي', 'Grade 7',  4),
    ('الصف الثاني الإعدادي','Grade 8',  5),
    ('الصف الثالث الإعدادي','Grade 9',  6)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS public.subjects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grade_id    UUID REFERENCES public.grades(id) ON DELETE SET NULL,
    name_ar     TEXT NOT NULL,
    name_en     TEXT,
    cover_image TEXT,
    color_hex   TEXT NOT NULL DEFAULT '3B82F6',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_subjects_grade ON public.subjects(grade_id);

CREATE TABLE IF NOT EXISTS public.subject_teachers (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id    UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
    teacher_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(subject_id, teacher_id)
);

CREATE TABLE IF NOT EXISTS public.enrollments (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id     UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    subject_id     UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
    access_code_id UUID,  -- FK added after access_codes table
    enrolled_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(student_id, subject_id)
);
CREATE INDEX IF NOT EXISTS idx_enrollments_student ON public.enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_subject ON public.enrollments(subject_id);

-- ─────────────────────────────────────────────────────────────
-- 4. LECTURES & VERSIONING
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.lectures (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id   UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
    teacher_id   UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    title_ar     TEXT NOT NULL,
    title_en     TEXT,
    description  TEXT,
    thumbnail    TEXT,
    order_num    INTEGER NOT NULL DEFAULT 1,
    is_published BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lectures_subject ON public.lectures(subject_id);
CREATE INDEX IF NOT EXISTS idx_lectures_teacher ON public.lectures(teacher_id);

CREATE TABLE IF NOT EXISTS public.lecture_versions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lecture_id     UUID NOT NULL REFERENCES public.lectures(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    snapshot_json  JSONB NOT NULL DEFAULT '{}',
    created_by     UUID REFERENCES public.profiles(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(lecture_id, version_number)
);

-- ─────────────────────────────────────────────────────────────
-- 5. DYNAMIC SECTION SYSTEM
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.section_types (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_key  TEXT UNIQUE NOT NULL,
    label_ar  TEXT NOT NULL,
    label_en  TEXT NOT NULL,
    icon      TEXT NOT NULL DEFAULT '📄',
    renderer  TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- Seed section types
INSERT INTO public.section_types (type_key, label_ar, label_en, icon, renderer) VALUES
    ('video',           'فيديو المحاضرة',      'Lecture Video',    '🎬', 'app.sections.video.render_video'),
    ('hw_review_video', 'فيديو مراجعة الواجب', 'HW Review Video',  '📹', 'app.sections.video.render_video'),
    ('quiz',            'اختبار',               'Quiz',             '📝', 'app.sections.quiz.render_quiz'),
    ('homework',        'واجب MCQ',             'Homework (MCQ)',   '📚', 'app.sections.homework.render_homework'),
    ('hw_upload',       'رفع ملف',              'Homework Upload',  '📎', 'app.sections.hw_upload.render_hw_upload'),
    ('pdf_notes',       'ملاحظات PDF',          'PDF Notes',        '📄', 'app.sections.pdf_notes.render_pdf'),
    ('attachments',     'مرفقات',               'Attachments',      '🗂️', 'app.sections.attachments.render_attachments'),
    ('links',           'روابط خارجية',         'External Links',   '🔗', 'app.sections.links.render_links'),
    ('discussion',      'نقاش',                 'Discussion',       '💬', 'app.sections.discussion.render_discussion')
ON CONFLICT (type_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.lecture_sections (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lecture_id   UUID NOT NULL REFERENCES public.lectures(id) ON DELETE CASCADE,
    section_type TEXT NOT NULL REFERENCES public.section_types(type_key),
    order_num    INTEGER NOT NULL DEFAULT 0,
    is_enabled   BOOLEAN NOT NULL DEFAULT true,
    config_json  JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lecture_sections_lecture ON public.lecture_sections(lecture_id);

CREATE TABLE IF NOT EXISTS public.section_versions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id     UUID NOT NULL REFERENCES public.lecture_sections(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    config_json    JSONB NOT NULL DEFAULT '{}',
    created_by     UUID REFERENCES public.profiles(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(section_id, version_number)
);

-- ─────────────────────────────────────────────────────────────
-- 6. ASSESSMENTS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.exams (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id        UUID REFERENCES public.subjects(id) ON DELETE CASCADE,
    lecture_id        UUID REFERENCES public.lectures(id) ON DELETE SET NULL,
    title             TEXT NOT NULL,
    duration_minutes  INTEGER NOT NULL DEFAULT 30,
    shuffle_questions BOOLEAN NOT NULL DEFAULT false,
    pass_score        INTEGER NOT NULL DEFAULT 60,
    show_answers      BOOLEAN NOT NULL DEFAULT true,
    created_by        UUID REFERENCES public.profiles(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.homework (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id   UUID REFERENCES public.subjects(id) ON DELETE CASCADE,
    lecture_id   UUID REFERENCES public.lectures(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    deadline     TIMESTAMPTZ,
    allow_upload BOOLEAN NOT NULL DEFAULT false,
    created_by   UUID REFERENCES public.profiles(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.questions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id        UUID REFERENCES public.exams(id) ON DELETE CASCADE,
    hw_id          UUID REFERENCES public.homework(id) ON DELETE CASCADE,
    question_text  TEXT NOT NULL,
    option_a       TEXT,
    option_b       TEXT,
    option_c       TEXT,
    option_d       TEXT,
    correct_answer TEXT NOT NULL,
    topic          TEXT,
    points         INTEGER NOT NULL DEFAULT 1,
    order_num      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.results (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    exam_id      UUID REFERENCES public.exams(id) ON DELETE SET NULL,
    hw_id        UUID REFERENCES public.homework(id) ON DELETE SET NULL,
    score        REAL,
    total        INTEGER,
    weak_topics  JSONB NOT NULL DEFAULT '[]',
    ai_feedback  TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_results_student ON public.results(student_id);

-- ─────────────────────────────────────────────────────────────
-- 7. ACCESS CODE SYSTEM V2
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.code_batches (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_name  TEXT NOT NULL,
    description TEXT,
    subject_id  UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
    total_codes INTEGER NOT NULL DEFAULT 0,
    max_uses    INTEGER NOT NULL DEFAULT 1,
    expires_at  TIMESTAMPTZ,
    created_by  UUID REFERENCES public.profiles(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.access_codes (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id   UUID REFERENCES public.code_batches(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
    code       TEXT UNIQUE NOT NULL,
    qr_path    TEXT,
    max_uses   INTEGER NOT NULL DEFAULT 1,
    uses_count INTEGER NOT NULL DEFAULT 0,
    is_active  BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_access_codes_code    ON public.access_codes(code);
CREATE INDEX IF NOT EXISTS idx_access_codes_subject ON public.access_codes(subject_id);
CREATE INDEX IF NOT EXISTS idx_access_codes_batch   ON public.access_codes(batch_id);

-- Add FK from enrollments to access_codes (now that table exists)
ALTER TABLE public.enrollments
    ADD COLUMN IF NOT EXISTS access_code_id UUID REFERENCES public.access_codes(id) ON DELETE SET NULL;

-- ─────────────────────────────────────────────────────────────
-- 8. PROGRESS TRACKING
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.student_section_progress (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    section_id   UUID NOT NULL REFERENCES public.lecture_sections(id) ON DELETE CASCADE,
    completed    BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,
    UNIQUE(student_id, section_id)
);
CREATE INDEX IF NOT EXISTS idx_ssp_student   ON public.student_section_progress(student_id);
CREATE INDEX IF NOT EXISTS idx_ssp_section   ON public.student_section_progress(section_id);

CREATE TABLE IF NOT EXISTS public.student_progress (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    lecture_id   UUID NOT NULL REFERENCES public.lectures(id) ON DELETE CASCADE,
    subject_id   UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
    progress_pct INTEGER NOT NULL DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
    is_completed BOOLEAN NOT NULL DEFAULT false,
    last_viewed  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(student_id, lecture_id)
);
CREATE INDEX IF NOT EXISTS idx_sp_student ON public.student_progress(student_id);
CREATE INDEX IF NOT EXISTS idx_sp_subject ON public.student_progress(subject_id);

-- ─────────────────────────────────────────────────────────────
-- 9. HW UPLOADS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.hw_uploads (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    hw_id        UUID NOT NULL REFERENCES public.homework(id) ON DELETE CASCADE,
    bucket_name  TEXT NOT NULL DEFAULT 'homework',
    file_path    TEXT NOT NULL,
    file_name    TEXT,
    public_url   TEXT,
    grade        REAL,
    feedback     TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────
-- 10. DISCUSSIONS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.discussions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id   UUID NOT NULL REFERENCES public.lecture_sections(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    parent_id    UUID REFERENCES public.discussions(id) ON DELETE CASCADE,
    content      TEXT NOT NULL,
    is_anonymous BOOLEAN NOT NULL DEFAULT false,
    reply_count  INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_disc_section    ON public.discussions(section_id);
CREATE INDEX IF NOT EXISTS idx_disc_parent     ON public.discussions(parent_id);
CREATE INDEX IF NOT EXISTS idx_disc_created_at ON public.discussions(created_at DESC);

-- Auto-update reply_count
CREATE OR REPLACE FUNCTION public.update_reply_count()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.parent_id IS NOT NULL THEN
        UPDATE public.discussions
        SET reply_count = reply_count + 1
        WHERE id = NEW.parent_id;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_reply_count ON public.discussions;
CREATE TRIGGER trg_reply_count
    AFTER INSERT ON public.discussions
    FOR EACH ROW EXECUTE FUNCTION public.update_reply_count();

-- ─────────────────────────────────────────────────────────────
-- 11. AUDIT LOGS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    action     TEXT NOT NULL,
    entity     TEXT,
    entity_id  UUID,
    metadata   JSONB NOT NULL DEFAULT '{}',
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_user      ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_created   ON public.audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action    ON public.audit_logs(action);

-- ─────────────────────────────────────────────────────────────
-- 12. ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────

-- profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS profiles_self   ON public.profiles;
DROP POLICY IF EXISTS profiles_manage ON public.profiles;
CREATE POLICY profiles_self   ON public.profiles FOR ALL  USING (id = auth.uid());
CREATE POLICY profiles_manage ON public.profiles FOR SELECT USING (public.has_permission('manage_users'));

-- subjects
ALTER TABLE public.subjects ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS subjects_read   ON public.subjects;
DROP POLICY IF EXISTS subjects_manage ON public.subjects;
CREATE POLICY subjects_read ON public.subjects FOR SELECT USING (
    is_active = true AND (
        public.has_permission('manage_subjects') OR
        EXISTS(SELECT 1 FROM public.enrollments e   WHERE e.subject_id = subjects.id AND e.student_id = auth.uid()) OR
        EXISTS(SELECT 1 FROM public.subject_teachers st WHERE st.subject_id = subjects.id AND st.teacher_id = auth.uid())
    )
);
CREATE POLICY subjects_manage ON public.subjects FOR ALL USING (public.has_permission('manage_subjects'));

-- lectures
ALTER TABLE public.lectures ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lectures_student ON public.lectures;
DROP POLICY IF EXISTS lectures_manage  ON public.lectures;
CREATE POLICY lectures_student ON public.lectures FOR SELECT USING (
    is_published = true AND
    EXISTS(SELECT 1 FROM public.enrollments e WHERE e.subject_id = lectures.subject_id AND e.student_id = auth.uid())
);
CREATE POLICY lectures_manage ON public.lectures FOR ALL USING (
    public.has_permission('manage_lectures') OR teacher_id = auth.uid()
);

-- lecture_sections
ALTER TABLE public.lecture_sections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sections_student ON public.lecture_sections;
DROP POLICY IF EXISTS sections_manage  ON public.lecture_sections;
CREATE POLICY sections_student ON public.lecture_sections FOR SELECT USING (
    EXISTS(
        SELECT 1 FROM public.lectures l
        JOIN public.enrollments e ON e.subject_id = l.subject_id
        WHERE l.id = lecture_sections.lecture_id
          AND e.student_id = auth.uid()
          AND l.is_published = true
    )
);
CREATE POLICY sections_manage ON public.lecture_sections FOR ALL USING (public.has_permission('manage_sections'));

-- enrollments
ALTER TABLE public.enrollments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS enroll_own    ON public.enrollments;
DROP POLICY IF EXISTS enroll_manage ON public.enrollments;
CREATE POLICY enroll_own    ON public.enrollments FOR SELECT USING (student_id = auth.uid());
CREATE POLICY enroll_manage ON public.enrollments FOR ALL    USING (public.has_permission('manage_subjects'));
CREATE POLICY enroll_insert ON public.enrollments FOR INSERT WITH CHECK (student_id = auth.uid());

-- student_section_progress
ALTER TABLE public.student_section_progress ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ssp_own     ON public.student_section_progress;
DROP POLICY IF EXISTS ssp_reports ON public.student_section_progress;
CREATE POLICY ssp_own     ON public.student_section_progress FOR ALL    USING (student_id = auth.uid());
CREATE POLICY ssp_reports ON public.student_section_progress FOR SELECT USING (public.has_permission('view_reports'));

-- student_progress
ALTER TABLE public.student_progress ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sp_own     ON public.student_progress;
DROP POLICY IF EXISTS sp_reports ON public.student_progress;
CREATE POLICY sp_own     ON public.student_progress FOR ALL    USING (student_id = auth.uid());
CREATE POLICY sp_reports ON public.student_progress FOR SELECT USING (public.has_permission('view_reports'));

-- results
ALTER TABLE public.results ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS results_own     ON public.results;
DROP POLICY IF EXISTS results_teacher ON public.results;
DROP POLICY IF EXISTS results_insert  ON public.results;
CREATE POLICY results_own    ON public.results FOR SELECT USING (student_id = auth.uid());
CREATE POLICY results_teacher ON public.results FOR SELECT USING (public.has_permission('view_reports'));
CREATE POLICY results_insert  ON public.results FOR INSERT WITH CHECK (student_id = auth.uid());

-- access_codes
ALTER TABLE public.access_codes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS codes_manage   ON public.access_codes;
DROP POLICY IF EXISTS codes_activate ON public.access_codes;
CREATE POLICY codes_manage   ON public.access_codes FOR ALL    USING (public.has_permission('manage_access_codes'));
CREATE POLICY codes_activate ON public.access_codes FOR SELECT USING (true);

-- code_batches
ALTER TABLE public.code_batches ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS batches_manage ON public.code_batches;
CREATE POLICY batches_manage ON public.code_batches FOR ALL USING (public.has_permission('manage_access_codes'));

-- discussions
ALTER TABLE public.discussions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS disc_read   ON public.discussions;
DROP POLICY IF EXISTS disc_insert ON public.discussions;
CREATE POLICY disc_read ON public.discussions FOR SELECT USING (
    EXISTS(
        SELECT 1 FROM public.lecture_sections ls
        JOIN public.lectures l ON ls.lecture_id = l.id
        JOIN public.enrollments e ON e.subject_id = l.subject_id
        WHERE ls.id = discussions.section_id AND e.student_id = auth.uid()
    ) OR public.has_permission('manage_discussions')
);
CREATE POLICY disc_insert ON public.discussions FOR INSERT WITH CHECK (user_id = auth.uid());

-- hw_uploads
ALTER TABLE public.hw_uploads ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS uploads_own    ON public.hw_uploads;
DROP POLICY IF EXISTS uploads_grade  ON public.hw_uploads;
CREATE POLICY uploads_own   ON public.hw_uploads FOR ALL    USING (student_id = auth.uid());
CREATE POLICY uploads_grade ON public.hw_uploads FOR SELECT USING (public.has_permission('grade_homework'));
CREATE POLICY uploads_update ON public.hw_uploads FOR UPDATE USING (public.has_permission('grade_homework'));

-- audit_logs
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_read   ON public.audit_logs;
DROP POLICY IF EXISTS audit_insert ON public.audit_logs;
CREATE POLICY audit_read   ON public.audit_logs FOR SELECT USING (public.has_permission('view_audit_log'));
CREATE POLICY audit_insert ON public.audit_logs FOR INSERT WITH CHECK (true);

-- grades, section_types, roles, permissions: public read
ALTER TABLE public.grades        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.section_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permissions   ENABLE ROW LEVEL SECURITY;

CREATE POLICY grades_read        ON public.grades        FOR SELECT USING (true);
CREATE POLICY section_types_read ON public.section_types FOR SELECT USING (true);
CREATE POLICY roles_read         ON public.roles         FOR SELECT USING (true);
CREATE POLICY permissions_read   ON public.permissions   FOR SELECT USING (true);

-- ─────────────────────────────────────────────────────────────
-- 13. REALTIME (enable for discussions)
-- ─────────────────────────────────────────────────────────────
ALTER PUBLICATION supabase_realtime ADD TABLE public.discussions;
ALTER PUBLICATION supabase_realtime ADD TABLE public.student_progress;

-- ─────────────────────────────────────────────────────────────
-- DONE ✅
-- ─────────────────────────────────────────────────────────────
SELECT 'EduVision v3.0 schema installed successfully! 🎓' AS status;
