import streamlit as st
from app.core.security import get_supabase, get_current_user_id
from translations import get_lang


def show_admin():
    lang = get_lang()
    sb   = get_supabase()
    uid  = get_current_user_id()

    with st.sidebar:
        st.markdown(f"### 👑 {'لوحة التحكم' if lang=='ar' else 'Admin Panel'}")
        pages = {
            "dashboard":    ("📊", "الرئيسية",     "Dashboard"),
            "users":        ("👥", "المستخدمين",   "Users"),
            "subjects":     ("📚", "المواد",        "Subjects"),
            "access_codes": ("🔑", "أكواد الوصول", "Access Codes"),
            "results":      ("📈", "النتائج",       "Results"),
            "audit":        ("📋", "سجل الأحداث",  "Audit Log"),
        }
        if "admin_page" not in st.session_state:
            st.session_state.admin_page = "dashboard"
        for key, (icon, ar, en) in pages.items():
            label  = f"{icon} {ar if lang=='ar' else en}"
            active = st.session_state.admin_page == key
            if st.button(label, use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.admin_page = key
                st.rerun()

    page = st.session_state.admin_page
    if   page == "dashboard":    _dashboard(sb, lang)
    elif page == "users":        _users(sb, lang, uid)
    elif page == "subjects":     _subjects(sb, lang, uid)
    elif page == "access_codes": _access_codes(sb, lang, uid)
    elif page == "results":      _results(sb, lang)
    elif page == "audit":        _audit(sb, lang)


# ── DASHBOARD ─────────────────────────────────────────────────
def _dashboard(sb, lang):
    st.title("📊 " + ("الرئيسية" if lang=="ar" else "Dashboard"))
    try:
        student_role_id = sb.table("roles").select("id").eq("name","student").single().execute().data["id"]
        teacher_role_id = sb.table("roles").select("id").eq("name","teacher").single().execute().data["id"]
        students = sb.table("user_roles").select("user_id", count="exact").eq("role_id", student_role_id).execute().count or 0
        teachers = sb.table("user_roles").select("user_id", count="exact").eq("role_id", teacher_role_id).execute().count or 0
        subjects = sb.table("subjects").select("id", count="exact").eq("is_active", True).execute().count or 0
        exams    = sb.table("exams").select("id", count="exact").execute().count or 0
    except Exception:
        students = teachers = subjects = exams = 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎓 الطلاب",     students)
    c2.metric("📚 المعلمون",   teachers)
    c3.metric("📖 المواد",      subjects)
    c4.metric("📝 الامتحانات", exams)
    st.divider()

    st.subheader("📈 " + ("آخر النتائج" if lang=="ar" else "Latest Results"))
    try:
        res = sb.table("results").select("submitted_at, score, total, profiles(full_name), exams(title)") \
                .order("submitted_at", desc=True).limit(10).execute()
        if res.data:
            import pandas as pd
            rows = []
            for r in res.data:
                pct = round(r["score"]/r["total"]*100) if r["total"] else 0
                rows.append({
                    "الطالب":  (r.get("profiles") or {}).get("full_name","—"),
                    "الامتحان":(r.get("exams") or {}).get("title","—"),
                    "الدرجة":  f"{r['score']}/{r['total']} ({pct}%)",
                    "التاريخ": str(r["submitted_at"])[:10],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد نتائج بعد")
    except Exception as e:
        st.error(f"خطأ: {e}")


# ── USERS ─────────────────────────────────────────────────────
def _users(sb, lang, uid):
    st.title("👥 " + ("المستخدمين" if lang=="ar" else "Users"))

    with st.expander("➕ إضافة مستخدم"):
        with st.form("add_user"):
            c1, c2 = st.columns(2)
            with c1:
                u_name  = st.text_input("الاسم الكامل")
                u_email = st.text_input("البريد الإلكتروني")
            with c2:
                u_role  = st.selectbox("الدور", ["teacher","co_admin","admin"])
                u_pass  = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("➕ إضافة", use_container_width=True):
                if all([u_name, u_email, u_pass]):
                    try:
                        from app.services.auth_service import AuthService
                        AuthService().admin_create_user(u_email, u_pass, u_name, u_role, uid)
                        st.success("✅ تم إضافة المستخدم")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.error("أدخل جميع البيانات")

    try:
        users = sb.table("profiles").select("id, full_name, language, created_at").execute().data or []
        roles_res = sb.table("user_roles").select("user_id, roles(name)").execute().data or []
        role_map = {r["user_id"]: r["roles"]["name"] for r in roles_res}
        import pandas as pd
        df = pd.DataFrame([{
            "الاسم":  u["full_name"],
            "الدور":  role_map.get(u["id"],"—"),
            "اللغة":  u.get("language","ar"),
            "تاريخ الانضمام": str(u["created_at"])[:10],
        } for u in users])
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"خطأ: {e}")


# ── SUBJECTS ──────────────────────────────────────────────────
def _subjects(sb, lang, uid):
    st.title("📚 " + ("المواد الدراسية" if lang=="ar" else "Subjects"))

    with st.expander("➕ إضافة مادة"):
        with st.form("add_subject"):
            c1, c2 = st.columns(2)
            with c1:
                s_ar    = st.text_input("اسم المادة (عربي)")
                s_en    = st.text_input("Subject Name (English)")
            with c2:
                grades  = sb.table("grades").select("*").order("order_num").execute().data or []
                g_opts  = {g["name_ar"]: g["id"] for g in grades}
                s_grade = st.selectbox("الصف", list(g_opts.keys()))
                s_color = st.color_picker("اللون", "#3B82F6")
            if st.form_submit_button("➕ إضافة", use_container_width=True):
                if s_ar:
                    sb.table("subjects").insert({
                        "name_ar": s_ar, "name_en": s_en or s_ar,
                        "grade_id": g_opts.get(s_grade),
                        "color_hex": s_color.replace("#",""),
                    }).execute()
                    st.success("✅ تمت الإضافة")
                    st.rerun()

    try:
        subs = sb.table("subjects").select("*, grades(name_ar)").eq("is_active",True).execute().data or []
        for sub in subs:
            c1, c2, c3 = st.columns([4,2,1])
            c1.markdown(f"**{sub['name_ar']}** · {(sub.get('grades') or {}).get('name_ar','—')}")
            c2.markdown(f"🎨 `#{sub['color_hex']}`")
            if c3.button("🗑️", key=f"ds_{sub['id']}"):
                sb.table("subjects").update({"is_active":False}).eq("id",sub["id"]).execute()
                st.rerun()
    except Exception as e:
        st.error(f"خطأ: {e}")


# ── ACCESS CODES ──────────────────────────────────────────────
def _access_codes(sb, lang, uid):
    st.title("🔑 " + ("أكواد الوصول" if lang=="ar" else "Access Codes"))
    from app.services.access_code_service import AccessCodeService
    from app.reports.excel_exporter import export_codes_excel
    svc = AccessCodeService()

    subs = sb.table("subjects").select("id, name_ar").eq("is_active",True).execute().data or []
    if not subs:
        st.info("لا توجد مواد. أضف مادة أولاً.")
        return
    sub_opts = {s["name_ar"]: s["id"] for s in subs}
    chosen   = st.selectbox("اختر المادة", list(sub_opts.keys()))
    sid      = sub_opts[chosen]

    with st.expander("🔑 توليد أكواد جديدة"):
        with st.form("gen_codes"):
            c1, c2, c3 = st.columns(3)
            with c1:
                b_name  = st.text_input("اسم الباتش", value="Batch 1")
                b_desc  = st.text_input("الوصف (اختياري)")
            with c2:
                qty      = st.number_input("عدد الأكواد", 1, 500, 10)
                max_uses = st.number_input("الحد الأقصى للاستخدام", 0, 100, 1, help="0=غير محدود")
            with c3:
                use_exp  = st.checkbox("تحديد تاريخ انتهاء")
                exp_date = st.date_input("تاريخ الانتهاء") if use_exp else None
            if st.form_submit_button("🚀 توليد", use_container_width=True):
                with st.spinner("جاري التوليد..."):
                    try:
                        svc.create_batch(sid, b_name, b_desc, int(qty),
                                         int(max_uses), exp_date, uid)
                        st.success(f"✅ تم توليد {qty} كود")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    batches = svc.get_subject_batches(sid)
    for batch in batches:
        stats = svc.get_batch_analytics(batch["id"])
        with st.expander(
            f"📦 {batch['batch_name']}  |  "
            f"✅ {stats.get('used',0)} مستخدم  |  "
            f"🔵 {stats.get('unused',0)} متاح  |  "
            f"📊 {stats.get('redemption_rate',0)}%"
        ):
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("إجمالي", stats.get("total",0))
            c2.metric("مستخدم", stats.get("used",0))
            c3.metric("متاح",   stats.get("unused",0))
            c4.metric("منتهي",  stats.get("expired",0))

            codes = svc.get_batch_codes(batch["id"])
            buf, fname = export_codes_excel(codes, batch["batch_name"], chosen)
            st.download_button(
                "📥 تحميل Excel", buf, file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"xl_{batch['id']}"
            )
            import pandas as pd
            df = pd.DataFrame([{
                "الكود": c["code"],
                "الاستخدام": f"{c['uses_count']}/{c['max_uses'] or '∞'}",
                "نشط": "✅" if c["is_active"] else "❌",
                "الانتهاء": str(c["expires_at"])[:10] if c["expires_at"] else "—",
            } for c in codes])
            st.dataframe(df, use_container_width=True, hide_index=True)


# ── RESULTS ───────────────────────────────────────────────────
def _results(sb, lang):
    st.title("📈 " + ("النتائج" if lang=="ar" else "Results"))
    try:
        res = sb.table("results")\
                .select("*, profiles(full_name), exams(title)")\
                .order("submitted_at", desc=True).limit(200).execute()
        rows = res.data or []
        if rows:
            import pandas as pd
            df = pd.DataFrame([{
                "الطالب":  (r.get("profiles") or {}).get("full_name","—"),
                "الامتحان":(r.get("exams") or {}).get("title","—"),
                "الدرجة":  f"{r['score']}/{r['total']}",
                "%":       f"{round(r['score']/r['total']*100) if r['total'] else 0}%",
                "التاريخ": str(r["submitted_at"])[:10],
            } for r in rows])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد نتائج")
    except Exception as e:
        st.error(f"خطأ: {e}")


# ── AUDIT LOG ─────────────────────────────────────────────────
def _audit(sb, lang):
    st.title("📋 " + ("سجل الأحداث" if lang=="ar" else "Audit Log"))
    try:
        res = sb.table("audit_logs")\
                .select("*, profiles(full_name)")\
                .order("created_at", desc=True).limit(300).execute()
        rows = res.data or []
        if rows:
            import pandas as pd
            df = pd.DataFrame([{
                "المستخدم": (r.get("profiles") or {}).get("full_name","—"),
                "الإجراء":  r["action"],
                "النوع":    r.get("entity","—"),
                "التفاصيل": str(r.get("metadata",{}))[:80],
                "الوقت":    str(r["created_at"])[:19],
            } for r in rows])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أحداث مسجلة")
    except Exception as e:
        st.error(f"خطأ: {e}")
