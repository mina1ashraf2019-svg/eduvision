from __future__ import annotations
import re
import streamlit as st
import pandas as pd
from app.core.security import (
    get_supabase_admin, get_current_user_id, has_permission
)
from app.services.credit_service import CreditService


def show_owner():
    uid  = get_current_user_id()
    sb   = get_supabase_admin()
    svc  = CreditService()

    with st.sidebar:
        st.markdown("### 👑 لوحة المالك")
        pages = {
            "dashboard":    ("📊", "الرئيسية"),
            "analytics":    ("📈", "التحليلات"),
            "credits":      ("💳", "إدارة Credits"),
            "roles":        ("🔐", "الأدوار والصلاحيات"),
            "revenue":      ("💰", "الإيرادات"),
            "activity":     ("📋", "سجل الأحداث"),
            "settings":     ("⚙️", "الإعدادات"),
        }
        if "owner_page" not in st.session_state:
            st.session_state.owner_page = "dashboard"
        for key, (icon, label) in pages.items():
            active = st.session_state.owner_page == key
            if st.button(f"{icon} {label}", use_container_width=True,
                         type="primary" if active else "secondary",
                         key=f"onav_{key}"):
                st.session_state.owner_page = key
                st.rerun()

    page = st.session_state.owner_page
    if   page == "dashboard":  _dashboard(sb, uid)
    elif page == "analytics":  _analytics(sb, svc)
    elif page == "credits":    _credits_management(sb, svc, uid)
    elif page == "roles":      _roles_management(sb, uid)
    elif page == "revenue":    _revenue(sb)
    elif page == "activity":   _activity(sb)
    elif page == "settings":   _settings(sb, uid)


# ─────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────
def _dashboard(sb, uid):
    st.title("📊 لوحة المالك")

    try:
        stats = sb.rpc("get_owner_dashboard_stats").execute().data or {}
    except Exception:
        stats = {}

    c1, c2, c3 = st.columns(3)
    c1.metric("🎓 الطلاب",       stats.get("total_students", 0))
    c2.metric("📚 المعلمون",     stats.get("total_teachers", 0))
    c3.metric("📖 المواد",       stats.get("total_subjects", 0))

    c4, c5, c6 = st.columns(3)
    c4.metric("💳 Credits صدرت",  stats.get("total_credits_issued", 0))
    c5.metric("🎬 محاضرات فُتحت", stats.get("total_lectures_opened", 0))
    c6.metric("💰 الإيرادات",     f"{stats.get('total_revenue', 0)} ج.م")

    if stats.get("active_alerts", 0) > 0:
        st.warning(f"⚠️ {stats['active_alerts']} تنبيه أمني يحتاج مراجعة")

    st.divider()
    st.subheader("📈 آخر الأحداث")
    try:
        logs = sb.table("audit_logs") \
                 .select("action, entity, created_at, profiles(full_name)") \
                 .order("created_at", desc=True).limit(10).execute().data or []
        if logs:
            df = pd.DataFrame([{
                "المستخدم": (r.get("profiles") or {}).get("full_name", "—"),
                "الإجراء":  r["action"],
                "النوع":    r.get("entity", "—"),
                "الوقت":    str(r["created_at"])[:16],
            } for r in logs])
            st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"خطأ: {e}")


# ─────────────────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────────────────
def _analytics(sb, svc: CreditService):
    st.title("📈 التحليلات")

    try:
        subs = sb.table("subjects").select("id, name_ar").eq("is_active", True).execute().data or []
    except Exception:
        subs = []

    if not subs:
        st.info("لا توجد مواد.")
        return

    sub_opts = {s["name_ar"]: s["id"] for s in subs}
    chosen   = st.selectbox("اختر المادة", list(sub_opts.keys()))
    sid      = sub_opts[chosen]

    stats = svc.get_subject_credit_stats(sid)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Credits صدرت",   stats.get("total_issued", 0))
    c2.metric("Credits استُخدمت", stats.get("total_used", 0))
    c3.metric("Credits متاحة",  stats.get("total_available", 0))
    c4.metric("محافظ نشطة",     stats.get("active_wallets", 0))

    st.divider()
    st.subheader("آخر حركات Credits")
    try:
        txns = sb.table("credit_transactions") \
                 .select("*, profiles(full_name), lectures(title_ar)") \
                 .eq("subject_id", sid) \
                 .order("created_at", desc=True).limit(50).execute().data or []
        if txns:
            df = pd.DataFrame([{
                "الطالب":     (r.get("profiles") or {}).get("full_name", "—"),
                "النوع":      {"credit": "إضافة ✅", "debit": "خصم 🔒", "adjustment": "تعديل ✏️"}.get(r["type"], r["type"]),
                "الكمية":     r["amount"],
                "الرصيد بعد": r["balance_after"],
                "البيان":     r.get("description", "—")[:40],
                "التاريخ":    str(r["created_at"])[:16],
            } for r in txns])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد حركات بعد.")
    except Exception as e:
        st.error(f"خطأ: {e}")


# ─────────────────────────────────────────────────────────
# CREDITS MANAGEMENT
# ─────────────────────────────────────────────────────────
def _credits_management(sb, svc: CreditService, uid: str):
    st.title("💳 إدارة Credits الطلاب")

    tab1, tab2 = st.tabs(["🔍 بحث طالب", "✏️ تعديل يدوي"])

    with tab1:
        search = st.text_input("بحث باسم الطالب")
        if search and len(search) >= 2:
            try:
                roles_res   = sb.table("user_roles").select("user_id, roles(name)").execute().data or []
                student_ids = [r["user_id"] for r in roles_res
                               if (r.get("roles") or {}).get("name") == "student"]
                students = sb.table("profiles") \
                             .select("id, full_name") \
                             .in_("id", student_ids) \
                             .ilike("full_name", f"%{search}%") \
                             .limit(20).execute().data or []

                for s in students:
                    with st.expander(f"👤 {s['full_name']}"):
                        wallets = svc.get_all_wallets_for_student(s["id"])
                        if wallets:
                            df = pd.DataFrame([{
                                "المادة":         (w.get("subjects") or {}).get("name_ar", "—"),
                                "Credits متاحة":  w["credits_available"],
                                "Credits مستخدمة": w["credits_used"],
                            } for w in wallets])
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.info("لا يوجد رصيد.")
            except Exception as e:
                st.error(f"خطأ: {e}")

    with tab2:
        st.subheader("✏️ تعديل يدوي للرصيد")
        with st.form("adjust_credits"):
            col1, col2 = st.columns(2)
            with col1:
                student_email = st.text_input("البريد الإلكتروني للطالب")
            with col2:
                try:
                    subs     = sb.table("subjects").select("id, name_ar").eq("is_active", True).execute().data or []
                    sub_opts = {s["name_ar"]: s["id"] for s in subs}
                    chosen   = st.selectbox("المادة", list(sub_opts.keys()))
                except Exception:
                    sub_opts = {}
                    chosen   = None

            amount = st.number_input("الكمية (موجب = إضافة، سالب = خصم)", -100, 100, 1)
            reason = st.text_input("السبب")

            if st.form_submit_button("✅ تطبيق التعديل", type="primary"):
                if student_email and chosen and reason:
                    try:
                        user = sb.table("profiles") \
                                 .select("id") \
                                 .eq("id",
                                     sb.auth.admin.get_user_by_email(student_email).user.id
                                 ).execute()
                        student_id = user.data[0]["id"] if user.data else None
                        if student_id:
                            ok, bal = svc.adjust_credits(
                                uid, student_id, sub_opts[chosen], amount, reason
                            )
                            if ok:
                                st.success(f"✅ تم التعديل · الرصيد الجديد: {bal}")
                            else:
                                st.error(bal)
                        else:
                            st.error("الطالب غير موجود")
                    except Exception as e:
                        st.error(f"خطأ: {e}")
                else:
                    st.error("أدخل كل البيانات")


# ─────────────────────────────────────────────────────────
# ROLES MANAGEMENT
# ─────────────────────────────────────────────────────────
def _roles_management(sb, uid: str):
    st.title("🔐 الأدوار والصلاحيات")

    tab1, tab2 = st.tabs(["📋 الأدوار الحالية", "➕ إنشاء دور"])

    with tab1:
        try:
            roles = sb.table("roles").select("*, role_permissions(permissions(name))").execute().data or []
            for role in roles:
                perms = [rp["permissions"]["name"]
                         for rp in (role.get("role_permissions") or [])
                         if rp.get("permissions")]
                with st.expander(f"**{role['name']}** — {len(perms)} صلاحية"):
                    st.caption(role.get("description", ""))
                    if perms:
                        cols = st.columns(3)
                        for i, p in enumerate(sorted(perms)):
                            cols[i % 3].markdown(f"• `{p}`")
                    else:
                        st.info("لا توجد صلاحيات.")

                    all_perms = sb.table("permissions").select("id, name, description").execute().data or []
                    perm_opts = {p["name"]: p["id"] for p in all_perms}
                    selected  = st.multiselect(
                        "تعديل الصلاحيات", list(perm_opts.keys()),
                        default=[p for p in perms if p in perm_opts],
                        key=f"perms_{role['id']}"
                    )
                    if st.button("💾 حفظ", key=f"save_role_{role['id']}"):
                        try:
                            sb.table("role_permissions").delete().eq("role_id", role["id"]).execute()
                            if selected:
                                sb.table("role_permissions").insert([
                                    {"role_id": role["id"], "permission_id": perm_opts[p]}
                                    for p in selected
                                ]).execute()
                            st.success("✅ تم حفظ الصلاحيات")
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ: {e}")
        except Exception as e:
            st.error(f"خطأ: {e}")

    with tab2:
        with st.form("create_role"):
            r_name = st.text_input("اسم الدور (بالإنجليزية، بدون مسافات)")
            r_desc = st.text_input("الوصف")
            if st.form_submit_button("➕ إنشاء"):
                r_name = re.sub(r'[^a-z0-9_]', '', r_name.lower().replace(' ', '_'))
                if r_name:
                    try:
                        sb.table("roles").insert({"name": r_name, "description": r_desc}).execute()
                        sb.table("audit_logs").insert({
                            "user_id": uid, "action": "role_created",
                            "entity": "role", "metadata": {"name": r_name}
                        }).execute()
                        st.success(f"✅ تم إنشاء الدور: {r_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"خطأ: {e}")
                else:
                    st.error("أدخل اسماً صالحاً")


# ─────────────────────────────────────────────────────────
# REVENUE
# ─────────────────────────────────────────────────────────
def _revenue(sb):
    st.title("💰 الإيرادات")
    try:
        invoices = sb.table("sales_invoices") \
                    .select("total_amount, payment_method, status, created_at") \
                    .order("created_at", desc=True).limit(200).execute().data or []
        if not invoices:
            st.info("لا توجد فواتير بعد.")
            return

        paid   = [i for i in invoices if i["status"] == "paid"]
        refund = [i for i in invoices if i["status"] == "refunded"]

        c1, c2, c3 = st.columns(3)
        c1.metric("💰 إجمالي الإيرادات",  f"{sum(i['total_amount'] for i in paid):.0f} ج.م")
        c2.metric("🧾 عدد الفواتير",        len(paid))
        c3.metric("↩️ المسترجعات",          len(refund))

        df = pd.DataFrame([{
            "المبلغ":        f"{i['total_amount']} ج.م",
            "طريقة الدفع":   i["payment_method"],
            "الحالة":         i["status"],
            "التاريخ":        str(i["created_at"])[:10],
        } for i in invoices])
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"خطأ: {e}")


# ─────────────────────────────────────────────────────────
# ACTIVITY LOG
# ─────────────────────────────────────────────────────────
def _activity(sb):
    st.title("📋 سجل الأحداث الكامل")
    try:
        logs = sb.table("audit_logs") \
                 .select("*, profiles(full_name)") \
                 .order("created_at", desc=True).limit(500).execute().data or []
        if logs:
            df = pd.DataFrame([{
                "المستخدم":  (r.get("profiles") or {}).get("full_name", "—"),
                "الإجراء":   r["action"],
                "النوع":     r.get("entity", "—"),
                "التفاصيل":  str(r.get("metadata", {}))[:60],
                "الوقت":     str(r["created_at"])[:19],
            } for r in logs])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أحداث.")
    except Exception as e:
        st.error(f"خطأ: {e}")


# ─────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────
def _settings(sb, uid: str):
    st.title("⚙️ إعدادات النظام")
    try:
        configs = {c["key"]: c["value"] for c in
                   (sb.table("system_config").select("*").execute().data or [])}
    except Exception:
        configs = {}

    with st.form("system_settings"):
        c1, c2 = st.columns(2)
        with c1:
            max_dev  = st.number_input("الحد الأقصى للأجهزة", 1, 10,
                                       int(configs.get("max_devices_per_student", 2)))
            exp_secs = st.number_input("صلاحية الفيديو (ثانية)", 60, 3600,
                                       int(configs.get("signed_url_expiry_seconds", 300)))
        with c2:
            dev_act  = st.selectbox("عند تجاوز حد الأجهزة", ["block", "warn"],
                                    index=0 if configs.get("device_limit_action", "block") == "block" else 1)
            watermark = st.checkbox("تفعيل الـ Watermark",
                                    value=configs.get("watermark_enabled", "true") == "true")

        if st.form_submit_button("💾 حفظ الإعدادات", type="primary"):
            updates = [
                ("max_devices_per_student",  str(max_dev)),
                ("signed_url_expiry_seconds", str(exp_secs)),
                ("device_limit_action",       dev_act),
                ("watermark_enabled",         str(watermark).lower()),
            ]
            try:
                for key, val in updates:
                    sb.table("system_config").upsert({
                        "key": key, "value": val, "updated_by": uid
                    }).execute()
                st.success("✅ تم حفظ الإعدادات")
            except Exception as e:
                st.error(f"خطأ: {e}")
