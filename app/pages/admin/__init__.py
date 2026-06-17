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
            "dashboard":    ("📊", "الرئيسية"),
            "users":        ("👥", "المستخدمين"),
            "subjects":     ("📚", "المواد"),
            "access_codes": ("🔑", "أكواد الوصول"),
            "attendance":   ("📋", "الحضور"),
            "sales":        ("💰", "المبيعات"),
            "security":     ("🔒", "الأمان"),
            "results":      ("📈", "النتائج"),
            "audit":        ("📋", "سجل الأحداث"),
        }
        if "admin_page" not in st.session_state:
            st.session_state.admin_page = "dashboard"
        for key, (icon, label) in pages.items():
            active = st.session_state.admin_page == key
            if st.button(f"{icon} {label}", use_container_width=True,
                         type="primary" if active else "secondary",
                         key=f"admin_nav_{key}"):
                st.session_state.admin_page = key
                st.rerun()

    page = st.session_state.admin_page

    if page == "dashboard":
        _dashboard(sb, lang)
    elif page == "users":
        _users(sb, lang, uid)
    elif page == "subjects":
        _subjects(sb, lang, uid)
    elif page == "access_codes":
        _access_codes(sb, lang, uid)
    elif page == "attendance":
        from app.pages.admin.attendance import show_attendance
        show_attendance()
    elif page == "sales":
        from app.pages.admin.sales import show_sales
        show_sales()
    elif page == "security":
        from app.pages.admin.security import show_security
        show_security()
    elif page == "results":
        _results(sb, lang)
    elif page == "audit":
        _audit(sb, lang)


def _dashboard(sb, lang):
    st.title("📊 الرئيسية")
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

    # Security alerts summary
    try:
        alerts = sb.table("security_alerts").select("id", count="exact").eq("resolved", False).execute().count or 0
        if alerts > 0:
            st.warning(f"⚠️ {alerts} تنبيه أمني يحتاج مراجعة")
    except Exception:
        pass

    st.divider()
    st.subheader("📈 آخر النتائج")
    try:
        res = sb.table("results").select("submitted_at, score, total, profiles(full_name), exams(title)")\
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
            st.dataframe(__import__("pandas").DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد نتائج بعد")
    except Exception as e:
        st.error(f"خطأ: {e}")


def _users(sb, lang, uid):
    st.title("👥 المستخدمين")
    with st.expander("➕ إضافة مستخدم"):
        with st.form("add_user"):
            c1, c2 = st.columns(2)
            with c1:
                u_name  = st.text_input("الاسم الكامل")
                u_email = st.text_input("البريد الإلكتروني")
            with c2:
                u_role  = st.selectbox("الدور", ["teacher","co_admin","admin","cashier"])
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
        users     = sb.table("profiles").select("id, full_name, language, account_status, created_at").execute().data or []
        roles_res = sb.table("user_roles").select("user_id, roles(name)").execute().data or []
        role_map  = {r["user_id"]: r["roles"]["name"] for r in roles_res}
        import pandas as pd
        df = pd.DataFrame([{
            "الاسم":   u["full_name"],
            "الدور":   role_map.get(u["id"],"—"),
            "الحالة":  u.get("account_status","active"),
            "تاريخ الانضمام": str(u["created_at"])[:10],
        } for u in users])
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"خطأ: {e}")


def _subjects(sb, lang, uid):
    st.title("📚 المواد الدراسية")

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
                else:
                    st.error("أدخل اسم المادة")

    try:
        # Fetch all teachers
        teacher_role_id = sb.table("roles").select("id").eq("name","teacher").single().execute().data["id"]
        teacher_user_ids = [r["user_id"] for r in (sb.table("user_roles").select("user_id").eq("role_id", teacher_role_id).execute().data or [])]

        all_teachers = []
        if teacher_user_ids:
            all_teachers = sb.table("profiles").select("id, full_name").in_("id", teacher_user_ids).execute().data or []
        teacher_map = {t["id"]: t["full_name"] for t in all_teachers}

        subs = sb.table("subjects").select("*, grades(name_ar)").eq("is_active", True).execute().data or []

        for sub in subs:
            sub_id = sub["id"]

            # Get current assigned teachers for this subject
            assigned = sb.table("subject_teachers").select("teacher_id").eq("subject_id", sub_id).execute().data or []
            assigned_ids = [a["teacher_id"] for a in assigned]
            assigned_names = [teacher_map.get(tid, "—") for tid in assigned_ids if tid in teacher_map]

            with st.expander(f"**{sub['name_ar']}** · {(sub.get('grades') or {}).get('name_ar','—')} · 🎨 #{sub.get('color_hex','')}", expanded=False):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(f"**المعلمون الحاليون:** {', '.join(assigned_names) if assigned_names else '—'}")

                    # Teacher assignment form
                    if all_teachers:
                        available_teachers = {t["full_name"]: t["id"] for t in all_teachers}
                        selected_names = st.multiselect(
                            "تعيين المعلمين",
                            options=list(available_teachers.keys()),
                            default=[teacher_map[tid] for tid in assigned_ids if tid in teacher_map],
                            key=f"teachers_{sub_id}"
                        )
                        if st.button("💾 حفظ المعلمين", key=f"save_teachers_{sub_id}"):
                            try:
                                selected_ids = [available_teachers[n] for n in selected_names]
                                # Remove all existing assignments
                                sb.table("subject_teachers").delete().eq("subject_id", sub_id).execute()
                                # Insert new assignments
                                if selected_ids:
                                    sb.table("subject_teachers").insert([
                                        {"subject_id": sub_id, "teacher_id": tid}
                                        for tid in selected_ids
                                    ]).execute()
                                st.success("✅ تم حفظ المعلمين")
                                st.rerun()
                            except Exception as e:
                                st.error(f"خطأ: {e}")
                    else:
                        st.info("لا يوجد معلمون مسجلون بعد.")

                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️ حذف المادة", key=f"ds_{sub_id}", type="secondary"):
                        sb.table("subjects").update({"is_active": False}).eq("id", sub_id).execute()
                        st.rerun()

    except Exception as e:
        st.error(f"خطأ: {e}")


def _access_codes(sb, lang, uid):
    st.title("🔑 أكواد الوصول")
    from app.services.access_code_service import AccessCodeService
    from app.reports.excel_exporter import export_codes_excel
    svc = AccessCodeService()

    subs = sb.table("subjects").select("id, name_ar").eq("is_active",True).execute().data or []
    if not subs:
        st.info("لا توجد مواد.")
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
                max_uses = st.number_input("الحد الأقصى للاستخدام", 0, 100, 1)
            with c3:
                use_exp  = st.checkbox("تحديد تاريخ انتهاء")
                exp_date = st.date_input("تاريخ الانتهاء") if use_exp else None
            if st.form_submit_button("🚀 توليد", use_container_width=True):
                with st.spinner("جاري التوليد..."):
                    try:
                        svc.create_batch(sid, b_name, b_desc, int(qty), int(max_uses), exp_date, uid)
                        st.success(f"✅ تم توليد {qty} كود")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    batches = svc.get_subject_batches(sid)
    for batch in batches:
        stats = svc.get_batch_analytics(batch["id"])
        with st.expander(
            f"📦 {batch['batch_name']} | ✅ {stats.get('used',0)} مستخدم | 🔵 {stats.get('unused',0)} متاح"
        ):
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("إجمالي", stats.get("total",0))
            c2.metric("مستخدم", stats.get("used",0))
            c3.metric("متاح",   stats.get("unused",0))
            c4.metric("معدل",   f"{stats.get('redemption_rate',0)}%")
            codes = svc.get_batch_codes(batch["id"])
            buf, fname = export_codes_excel(codes, batch["batch_name"], chosen)
            st.download_button("📥 Excel", buf, file_name=fname,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key=f"xl_{batch['id']}")
            import pandas as pd
            df = pd.DataFrame([{
                "الكود": c["code"],
                "الاستخدام": f"{c['uses_count']}/{c['max_uses'] or '∞'}",
                "نشط": "✅" if c["is_active"] else "❌",
                "الانتهاء": str(c["expires_at"])[:10] if c["expires_at"] else "—",
            } for c in codes])
            st.dataframe(df, use_container_width=True, hide_index=True)


def _results(sb, lang):
    st.title("📈 النتائج")
    try:
        res = sb.table("results").select("*, profiles(full_name), exams(title)")\
                .order("submitted_at", desc=True).limit(200).execute()
        if res.data:
            import pandas as pd
            df = pd.DataFrame([{
                "الطالب":  (r.get("profiles") or {}).get("full_name","—"),
                "الامتحان":(r.get("exams") or {}).get("title","—"),
                "الدرجة":  f"{r['score']}/{r['total']}",
                "%":       f"{round(r['score']/r['total']*100) if r['total'] else 0}%",
                "التاريخ": str(r["submitted_at"])[:10],
            } for r in res.data])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد نتائج")
    except Exception as e:
        st.error(f"خطأ: {e}")


def _audit(sb, lang):
    st.title("📋 سجل الأحداث")
    try:
        res = sb.table("audit_logs").select("*, profiles(full_name)")\
                .order("created_at", desc=True).limit(300).execute()
        if res.data:
            import pandas as pd
            df = pd.DataFrame([{
                "المستخدم": (r.get("profiles") or {}).get("full_name","—"),
                "الإجراء":  r["action"],
                "النوع":    r.get("entity","—"),
                "التفاصيل": str(r.get("metadata",{}))[:80],
                "الوقت":    str(r["created_at"])[:19],
            } for r in res.data])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أحداث")
    except Exception as e:
        st.error(f"خطأ: {e}")
