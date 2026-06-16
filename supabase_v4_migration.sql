-- ============================================================
-- EduVision LMS v4.0 — Security & Operations Migration
-- Run in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- ─────────────────────────────────────────────────────────────
-- M-16: RBAC EXPANSION
-- ─────────────────────────────────────────────────────────────

-- Add namespace + display_name to permissions
ALTER TABLE public.permissions
    ADD COLUMN IF NOT EXISTS namespace    TEXT DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS display_name TEXT;

-- New roles
INSERT INTO public.roles (name, description) VALUES
    ('cashier', 'Sells access codes, generates invoices, handles payments'),
    ('parent',  'Read-only portal: child attendance, grades, activity')
ON CONFLICT (name) DO NOTHING;

-- New permissions
INSERT INTO public.permissions (name, namespace, display_name) VALUES
    ('devices.view',              'devices',    'View Devices'),
    ('devices.remove',            'devices',    'Remove Devices'),
    ('devices.block',             'devices',    'Block Devices'),
    ('devices.reset',             'devices',    'Reset Device Limit'),
    ('security.view_alerts',      'security',   'View Security Alerts'),
    ('security.resolve_alerts',   'security',   'Resolve Alerts'),
    ('security.freeze_account',   'security',   'Freeze Account'),
    ('security.unfreeze_account', 'security',   'Unfreeze Account'),
    ('attendance.view',           'attendance', 'View Attendance'),
    ('attendance.edit',           'attendance', 'Edit Attendance'),
    ('attendance.export',         'attendance', 'Export Attendance'),
    ('attendance.manual_checkin', 'attendance', 'Manual Check-In'),
    ('sales.create_invoice',      'sales',      'Create Invoice'),
    ('sales.sell_codes',          'sales',      'Sell Access Codes'),
    ('sales.refund',              'sales',      'Refund Transaction'),
    ('sales.view_reports',        'sales',      'View Sales Reports'),
    ('sales.manage_discounts',    'sales',      'Manage Discounts'),
    ('cards.view',                'cards',      'View Student Cards'),
    ('cards.generate',            'cards',      'Generate Student Cards'),
    ('cards.print',               'cards',      'Print Student Cards'),
    ('cards.revoke',              'cards',      'Revoke Student Cards'),
    ('codes.generate',            'codes',      'Generate Access Codes'),
    ('codes.export',              'codes',      'Export Access Codes'),
    ('codes.expire',              'codes',      'Expire Access Codes'),
    ('codes.analytics',           'codes',      'View Code Analytics'),
    ('sessions.view',             'sessions',   'View Active Sessions'),
    ('sessions.terminate',        'sessions',   'Terminate Sessions'),
    ('parent.view_child',         'parent',     'View Child Data')
ON CONFLICT (name) DO NOTHING;

-- Assign permissions to roles
DO $$
DECLARE
    r_admin    UUID := (SELECT id FROM public.roles WHERE name = 'admin');
    r_co_admin UUID := (SELECT id FROM public.roles WHERE name = 'co_admin');
    r_teacher  UUID := (SELECT id FROM public.roles WHERE name = 'teacher');
    r_cashier  UUID := (SELECT id FROM public.roles WHERE name = 'cashier');
    r_parent   UUID := (SELECT id FROM public.roles WHERE name = 'parent');
BEGIN
    -- Admin: all permissions
    INSERT INTO public.role_permissions (role_id, permission_id)
    SELECT r_admin, id FROM public.permissions
    ON CONFLICT DO NOTHING;

    -- Co-Admin: most except freeze/unfreeze/refund/devices.block
    INSERT INTO public.role_permissions (role_id, permission_id)
    SELECT r_co_admin, id FROM public.permissions
    WHERE name NOT IN ('security.freeze_account','security.unfreeze_account',
                       'sales.refund','devices.block','devices.reset','manage_roles')
    ON CONFLICT DO NOTHING;

    -- Teacher: attendance + cards view/print
    INSERT INTO public.role_permissions (role_id, permission_id)
    SELECT r_teacher, id FROM public.permissions
    WHERE name IN ('attendance.view','attendance.manual_checkin',
                   'cards.view','cards.print')
    ON CONFLICT DO NOTHING;

    -- Cashier: sales + codes + cards
    INSERT INTO public.role_permissions (role_id, permission_id)
    SELECT r_cashier, id FROM public.permissions
    WHERE name IN ('sales.create_invoice','sales.sell_codes','sales.view_reports',
                   'codes.generate','codes.export','codes.analytics',
                   'cards.view','cards.generate','cards.print')
    ON CONFLICT DO NOTHING;

    -- Parent: view child only
    INSERT INTO public.role_permissions (role_id, permission_id)
    SELECT r_parent, id FROM public.permissions
    WHERE name IN ('parent.view_child','attendance.view')
    ON CONFLICT DO NOTHING;
END;
$$;

-- ─────────────────────────────────────────────────────────────
-- M-17: SYSTEM CONFIG + DEVICE MANAGEMENT
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.system_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_by UUID REFERENCES public.profiles(id),
    updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO public.system_config (key, value) VALUES
    ('max_devices_per_student',   '2'),
    ('max_sessions_per_student',  '1'),
    ('allow_multiple_sessions',   'false'),
    ('watermark_enabled',         'true'),
    ('signed_url_expiry_seconds', '300'),
    ('device_limit_action',       'block')
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.student_devices (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id         UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    device_fingerprint TEXT NOT NULL,
    device_name        TEXT,
    platform           TEXT,
    browser            TEXT,
    ip_address         TEXT,
    first_seen         TIMESTAMPTZ DEFAULT now(),
    last_seen          TIMESTAMPTZ DEFAULT now(),
    is_blocked         BOOLEAN NOT NULL DEFAULT false,
    blocked_by         UUID REFERENCES public.profiles(id),
    blocked_at         TIMESTAMPTZ,
    UNIQUE(student_id, device_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_sd_student ON public.student_devices(student_id);
CREATE INDEX IF NOT EXISTS idx_sd_fingerprint ON public.student_devices(device_fingerprint);

-- ─────────────────────────────────────────────────────────────
-- M-18: SESSION MANAGEMENT
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.active_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    device_id       UUID REFERENCES public.student_devices(id) ON DELETE SET NULL,
    session_token   TEXT UNIQUE NOT NULL,
    ip_address      TEXT,
    user_agent      TEXT,
    started_at      TIMESTAMPTZ DEFAULT now(),
    last_active     TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    terminated_by   UUID REFERENCES public.profiles(id),
    terminated_at   TIMESTAMPTZ,
    termination_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_as_student   ON public.active_sessions(student_id);
CREATE INDEX IF NOT EXISTS idx_as_active    ON public.active_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_as_token     ON public.active_sessions(session_token);

-- ─────────────────────────────────────────────────────────────
-- M-19: SECURITY ALERTS + LOGIN HISTORY
-- ─────────────────────────────────────────────────────────────

-- Add account_status to profiles
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS account_status TEXT NOT NULL DEFAULT 'active'
    CHECK (account_status IN ('active','frozen','suspended','deleted'));

CREATE TABLE IF NOT EXISTS public.login_history (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    email        TEXT,
    ip_address   TEXT,
    user_agent   TEXT,
    device_fingerprint TEXT,
    success      BOOLEAN NOT NULL DEFAULT false,
    failure_reason TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lh_user    ON public.login_history(user_id);
CREATE INDEX IF NOT EXISTS idx_lh_created ON public.login_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lh_ip      ON public.login_history(ip_address);

CREATE TABLE IF NOT EXISTS public.security_alerts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    alert_type   TEXT NOT NULL,
    -- alert_type values:
    -- device_limit_exceeded | concurrent_session | suspicious_location
    -- multiple_failed_logins | account_sharing_detected | rapid_switching
    severity     TEXT NOT NULL DEFAULT 'medium'
                 CHECK (severity IN ('low','medium','high','critical')),
    details      JSONB DEFAULT '{}',
    resolved     BOOLEAN NOT NULL DEFAULT false,
    resolved_by  UUID REFERENCES public.profiles(id),
    resolved_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sa_student  ON public.security_alerts(student_id);
CREATE INDEX IF NOT EXISTS idx_sa_resolved ON public.security_alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_sa_type     ON public.security_alerts(alert_type);

-- ─────────────────────────────────────────────────────────────
-- M-20: ATTENDANCE SYSTEM
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.attendance_records (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    subject_id   UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
    lecture_id   UUID REFERENCES public.lectures(id) ON DELETE SET NULL,
    date         DATE NOT NULL DEFAULT CURRENT_DATE,
    status       TEXT NOT NULL DEFAULT 'present'
                 CHECK (status IN ('present','absent','late','excused')),
    check_in_at  TIMESTAMPTZ,
    check_out_at TIMESTAMPTZ,
    method       TEXT DEFAULT 'manual'
                 CHECK (method IN ('qr','manual','auto')),
    recorded_by  UUID REFERENCES public.profiles(id),
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(student_id, subject_id, date)
);
CREATE INDEX IF NOT EXISTS idx_att_student ON public.attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_att_subject ON public.attendance_records(subject_id);
CREATE INDEX IF NOT EXISTS idx_att_date    ON public.attendance_records(date DESC);

-- ─────────────────────────────────────────────────────────────
-- M-21: SALES & CASHIER SYSTEM
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.sales_invoices (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number TEXT UNIQUE NOT NULL,
    cashier_id     UUID NOT NULL REFERENCES public.profiles(id),
    student_id     UUID REFERENCES public.profiles(id),
    student_name   TEXT,      -- for walk-in customers
    student_phone  TEXT,
    subtotal       NUMERIC(10,2) NOT NULL DEFAULT 0,
    discount_pct   NUMERIC(5,2) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_amount   NUMERIC(10,2) NOT NULL DEFAULT 0,
    payment_method TEXT DEFAULT 'cash'
                   CHECK (payment_method IN ('cash','card','transfer','other')),
    status         TEXT DEFAULT 'paid'
                   CHECK (status IN ('paid','refunded','cancelled','pending')),
    notes          TEXT,
    refunded_by    UUID REFERENCES public.profiles(id),
    refunded_at    TIMESTAMPTZ,
    refund_reason  TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_inv_cashier ON public.sales_invoices(cashier_id);
CREATE INDEX IF NOT EXISTS idx_inv_student ON public.sales_invoices(student_id);
CREATE INDEX IF NOT EXISTS idx_inv_created ON public.sales_invoices(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inv_status  ON public.sales_invoices(status);

-- Auto-generate invoice number
CREATE OR REPLACE FUNCTION public.generate_invoice_number()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.invoice_number := 'INV-' ||
        TO_CHAR(now(), 'YYYYMMDD') || '-' ||
        LPAD(NEXTVAL('invoice_seq')::TEXT, 4, '0');
    RETURN NEW;
END;
$$;

CREATE SEQUENCE IF NOT EXISTS invoice_seq START 1;

DROP TRIGGER IF EXISTS trg_invoice_number ON public.sales_invoices;
CREATE TRIGGER trg_invoice_number
    BEFORE INSERT ON public.sales_invoices
    FOR EACH ROW
    WHEN (NEW.invoice_number IS NULL OR NEW.invoice_number = '')
    EXECUTE FUNCTION public.generate_invoice_number();

CREATE TABLE IF NOT EXISTS public.invoice_items (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id   UUID NOT NULL REFERENCES public.sales_invoices(id) ON DELETE CASCADE,
    subject_id   UUID REFERENCES public.subjects(id),
    subject_name TEXT NOT NULL,
    batch_id     UUID REFERENCES public.code_batches(id),
    quantity     INTEGER NOT NULL DEFAULT 1,
    unit_price   NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_price  NUMERIC(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.sold_codes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id   UUID NOT NULL REFERENCES public.sales_invoices(id) ON DELETE CASCADE,
    code_id      UUID NOT NULL REFERENCES public.access_codes(id),
    student_id   UUID REFERENCES public.profiles(id),
    sold_at      TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────
-- M-22: PARENT PORTAL
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.parent_student_links (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    student_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    relation     TEXT DEFAULT 'parent',
    is_active    BOOLEAN NOT NULL DEFAULT true,
    linked_by    UUID REFERENCES public.profiles(id),
    linked_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE(parent_id, student_id)
);

-- ─────────────────────────────────────────────────────────────
-- RLS POLICIES (v4 tables)
-- ─────────────────────────────────────────────────────────────

-- system_config: admin read/write, all read
ALTER TABLE public.system_config ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS config_read   ON public.system_config;
DROP POLICY IF EXISTS config_manage ON public.system_config;
CREATE POLICY config_read   ON public.system_config FOR SELECT USING (true);
CREATE POLICY config_manage ON public.system_config FOR ALL
    USING (public.has_permission('manage_subjects'));

-- student_devices: student sees own, admin sees all
ALTER TABLE public.student_devices ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS devices_own    ON public.student_devices;
DROP POLICY IF EXISTS devices_manage ON public.student_devices;
CREATE POLICY devices_own    ON public.student_devices FOR ALL    USING (student_id = auth.uid());
CREATE POLICY devices_manage ON public.student_devices FOR SELECT USING (public.has_permission('devices.view'));
CREATE POLICY devices_block  ON public.student_devices FOR UPDATE USING (public.has_permission('devices.block'));

-- active_sessions: student sees own, admin manages
ALTER TABLE public.active_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sessions_own    ON public.active_sessions;
DROP POLICY IF EXISTS sessions_manage ON public.active_sessions;
CREATE POLICY sessions_own    ON public.active_sessions FOR SELECT USING (student_id = auth.uid());
CREATE POLICY sessions_manage ON public.active_sessions FOR ALL    USING (public.has_permission('sessions.view'));

-- login_history: admin only
ALTER TABLE public.login_history ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS lh_own    ON public.login_history;
DROP POLICY IF EXISTS lh_manage ON public.login_history;
CREATE POLICY lh_own    ON public.login_history FOR SELECT USING (user_id = auth.uid());
CREATE POLICY lh_manage ON public.login_history FOR SELECT USING (public.has_permission('security.view_alerts'));
CREATE POLICY lh_insert ON public.login_history FOR INSERT WITH CHECK (true);

-- security_alerts: admin sees all, student sees own
ALTER TABLE public.security_alerts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sa_own    ON public.security_alerts;
DROP POLICY IF EXISTS sa_manage ON public.security_alerts;
CREATE POLICY sa_own    ON public.security_alerts FOR SELECT USING (student_id = auth.uid());
CREATE POLICY sa_manage ON public.security_alerts FOR ALL    USING (public.has_permission('security.view_alerts'));

-- attendance: student sees own, teacher/admin manage
ALTER TABLE public.attendance_records ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS att_own    ON public.attendance_records;
DROP POLICY IF EXISTS att_view   ON public.attendance_records;
DROP POLICY IF EXISTS att_manage ON public.attendance_records;
CREATE POLICY att_own    ON public.attendance_records FOR SELECT USING (student_id = auth.uid());
CREATE POLICY att_view   ON public.attendance_records FOR SELECT USING (public.has_permission('attendance.view'));
CREATE POLICY att_manage ON public.attendance_records FOR ALL    USING (public.has_permission('attendance.edit'));
CREATE POLICY att_insert ON public.attendance_records FOR INSERT WITH CHECK (public.has_permission('attendance.manual_checkin'));

-- sales_invoices: cashier/admin
ALTER TABLE public.sales_invoices ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS inv_manage ON public.sales_invoices;
DROP POLICY IF EXISTS inv_own    ON public.sales_invoices;
CREATE POLICY inv_manage ON public.sales_invoices FOR ALL    USING (public.has_permission('sales.view_reports'));
CREATE POLICY inv_own    ON public.sales_invoices FOR SELECT USING (cashier_id = auth.uid());
CREATE POLICY inv_insert ON public.sales_invoices FOR INSERT WITH CHECK (public.has_permission('sales.create_invoice'));

-- invoice_items + sold_codes
ALTER TABLE public.invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sold_codes    ENABLE ROW LEVEL SECURITY;
CREATE POLICY ii_manage ON public.invoice_items FOR ALL USING (public.has_permission('sales.view_reports'));
CREATE POLICY sc_manage ON public.sold_codes    FOR ALL USING (public.has_permission('sales.view_reports'));

-- parent_student_links: parent sees own, admin manages
ALTER TABLE public.parent_student_links ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS psl_own    ON public.parent_student_links;
DROP POLICY IF EXISTS psl_manage ON public.parent_student_links;
CREATE POLICY psl_own    ON public.parent_student_links FOR SELECT USING (parent_id = auth.uid());
CREATE POLICY psl_manage ON public.parent_student_links FOR ALL    USING (public.has_permission('manage_users'));

-- ─────────────────────────────────────────────────────────────
-- INDEXES (performance)
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_att_student_date ON public.attendance_records(student_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_inv_date         ON public.sales_invoices(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sa_student_open  ON public.security_alerts(student_id) WHERE NOT resolved;

-- ─────────────────────────────────────────────────────────────
-- DONE ✅
-- ─────────────────────────────────────────────────────────────
SELECT 'EduVision v4.0 Security & Operations schema installed! 🔒' AS status;
