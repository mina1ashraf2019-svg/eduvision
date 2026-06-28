import re
import streamlit as st
from app.core.security import get_supabase, get_current_user_id
from app.services.progress_service import ProgressService
from app.sections import render_section
from translations import get_lang


def _safe_color(hex_str: str) -> str:
    """Sanitize color_hex — prevents XSS via unsafe HTML injection."""
    clean = re.sub(r'[^0-9A-Fa-f]', '', str(hex_str or ""))
    return clean[:6] if len(clean) >= 6 else "3B82F6"


def show_student():
    lang  = get_lang()
    sb    = get_supabase()
    uid   = get_current_user_id()
    prog  = ProgressService()

    with st.sidebar:
        st.markdown(f"### 🎓 {'لوحة الطالب' if lang=='ar' else 'Student Panel'}")
        if st.button("🏠 " + ("الرئيسية" if lang=="ar" else "Home"),
                     key="stu_home", use_container_width=True):
            st.session_state.student_page = "home"
            st.session_state.pop("active_subject", None)
            st.session_state.pop("active_lecture", None)
            st.rerun()
        if st.button("📊 " + ("نتائجي" if lang=="ar" else "My Results"),
                     key="stu_results", use_container_width=True):
            st.session_state.student_page = "results"
            st.session_state.pop("active_subject", None)
            st.session_state.pop("active_lecture", None)
            st.rerun()
        if st.button("📱 " + ("حضور QR" if lang=="ar" else "QR Check-in"),
                     key="stu_qr", use_container_width=True):
            st.session_state.student_page = "qr_scan"
            st.session_state.pop("active_subject", None)
            st.session_state.pop("active_lecture", None)
            st.rerun()
        if st.button("🔑 " + ("تفعيل كود" if lang=="ar" else "Activate Code"),
                     key="stu_activate", use_container_width=True):
            st.session_state.student_page = "activate"
            st.session_state.pop("active_subject", None)
            st.session_state.pop("active_lecture", None)
            st.rerun()

    student_page  = st.session_state.get("student_page", "home")
    active_subject = st.session_state.get("active_subject")
    active_lecture = st.session_state.get("active_lecture")

    if student_page == "results":
        _my_results(sb, lang, uid)
    elif student_page == "activate":
        _activate_code(sb, lang, uid)
    elif student_page == "qr_scan":
        from app.pages.student.qr_scan import show_qr_scan
        show_qr_scan()
    elif active_lecture:
        _lecture_view(sb, lang, uid, active_lecture, prog)
    elif active_subject:
        _subject_view(sb, lang, uid, active_subject, prog)
    else:
        _dashboard(sb, lang, uid, prog)


# ── DASHBOARD ─────────────────────────────────────────────────
def _dashboard(sb, lang, uid, prog):
    user = st.session_state.user
    st.title(f"👋 {'أهلاً' if lang=='ar' else 'Welcome'}, {user['full_name']}!")

    try:
        enroll_res = sb.table("enrollments")\
                       .select("subject_id, subjects(id, name_ar, name_en, color_hex, grades(name_ar))")\
                       .eq("student_id", uid).execute()
        enrolled = [r["subjects"] for r in (enroll_res.data or []) if r.get("subjects")]
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not enrolled:
        st.info("🔒 لم تنضم لأي مادة بعد.")
        _activate_code(sb, lang, uid)
        return

    st.subheader("📚 " + ("موادي" if lang=="ar" else "My Subjects"))
    cols = st.columns(3)
    for i, sub in enumerate(enrolled):
        subject_prog = prog.get_subject_progress(uid, sub["id"])
        color = _safe_color(sub.get("color_hex", "3B82F6"))
        grade = (sub.get("grades") or {}).get("name_ar", "")
        with cols[i % 3]:
            st.markdown(f"""
            <div style="border-top:5px solid #{color};border-radius:12px;
                        padding:20px 16px 12px;background:#F8FAFC;
                        box-shadow:0 2px 10px rgba(0,0,0,0.07);margin-bottom:4px">
                <div style="font-size:1.1rem;font-weight:800;color:#0F2D6B;margin-bottom:4px">
                    {sub['name_ar']}
                </div>
                <div style="color:#6B7280;font-size:0.82rem;margin-bottom:10px">{grade}</div>
                <div style="background:#E2E8F0;border-radius:99px;height:6px;margin-bottom:6px">
                    <div style="background:#{color};width:{subject_prog}%;height:6px;border-radius:99px"></div>
                </div>
                <div style="color:#6B7280;font-size:0.78rem">{subject_prog}% مكتمل</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📖 فتح", key=f"open_sub_{sub['id']}_{i}",
                         use_container_width=True):
                st.session_state.active_subject = sub["id"]
                st.session_state.student_page   = "home"
                st.rerun()


# ── SUBJECT VIEW ──────────────────────────────────────────────
def _subject_view(sb, lang, uid, subject_id, prog):
    try:
        sub = sb.table("subjects").select("name_ar").eq("id", subject_id).single().execute()
        sub_name = sub.data["name_ar"] if sub.data else "المادة"
    except Exception:
        sub_name = "المادة"

    st.title(f"📚 {sub_name}")
    if st.button("← رجوع", key="back_from_subject"):
        st.session_state.pop("active_subject", None)
        st.session_state.pop("active_teacher", None)
        st.session_state.pop("view_lecture_list", None)
        st.rerun()
    st.divider()

    try:
        t_res = sb.table("subject_teachers")\
                  .select("teacher_id, display_order, profiles(id, full_name, bio)")\
                  .eq("subject_id", subject_id)\
                  .order("display_order").execute()
        teachers = [r["profiles"] for r in (t_res.data or []) if r.get("profiles")]
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not teachers:
        st.info("لم يتم تعيين معلمين بعد.")
        return

    st.subheader("👨‍🏫 المعلمون")
    cols = st.columns(min(len(teachers), 3))
    for i, teacher in enumerate(teachers):
        lec_count = 0
        try:
            lc = sb.table("lectures").select("id", count="exact")\
                   .eq("subject_id", subject_id)\
                   .eq("teacher_id", teacher["id"])\
                   .eq("is_published", True).execute()
            lec_count = lc.count or 0
        except Exception:
            pass

        with cols[i % 3]:
            initials = teacher["full_name"][0].upper() if teacher.get("full_name") else "?"
            st.markdown(f"""
            <div style="text-align:center;padding:24px 16px;border-radius:12px;
                        border:1.5px solid #E2E8F0;background:#fff;margin-bottom:8px">
                <div style="width:64px;height:64px;border-radius:50%;background:#3B82F6;
                            display:flex;align-items:center;justify-content:center;
                            font-size:1.8rem;font-weight:900;color:white;margin:0 auto 10px">
                    {initials}
                </div>
                <div style="font-weight:700;font-size:1rem;color:#0F2D6B">{teacher['full_name']}</div>
                <div style="color:#3B82F6;font-size:0.82rem;margin-top:8px">
                    📖 {lec_count} محاضرة
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("عرض المحاضرات", key=f"view_t_{teacher['id']}_{i}",
                         use_container_width=True):
                st.session_state.active_teacher    = teacher["id"]
                st.session_state.view_lecture_list = True
                st.rerun()

    if st.session_state.get("view_lecture_list") and st.session_state.get("active_teacher"):
        _lecture_list(sb, lang, uid, subject_id, st.session_state.active_teacher, prog)


# ── LECTURE LIST ──────────────────────────────────────────────
def _lecture_list(sb, lang, uid, subject_id, teacher_id, prog):
    st.divider()
    st.subheader("🎬 المحاضرات")

    try:
        lecs = sb.table("lectures").select("*")\
                 .eq("subject_id", subject_id)\
                 .eq("teacher_id", teacher_id)\
                 .eq("is_published", True)\
                 .order("order_num").execute().data or []
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not lecs:
        st.info("لا توجد محاضرات منشورة بعد.")
        return

    progress_map = prog.get_all_progress_for_subject(uid, subject_id)

    for idx, lec in enumerate(lecs):
        p    = progress_map.get(lec["id"], {})
        pct  = p.get("progress_pct", 0)
        done = p.get("is_completed", False)
        icon = "✅" if done else ("🔵" if pct > 0 else "⚪")

        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{icon} {lec['title_ar']}**")
            if lec.get("description"):
                st.caption(lec["description"])
            st.progress(pct / 100)
        with c2:
            if st.button("▶️ فتح", key=f"lec_{lec['id']}_{idx}",
                         use_container_width=True):
                st.session_state.active_lecture = lec["id"]
                st.rerun()
        st.divider()


# ── LECTURE VIEW ──────────────────────────────────────────────
def _lecture_view(sb, lang, uid, lecture_id, prog):
    if st.button("← رجوع", key="back_from_lecture"):
        st.session_state.pop("active_lecture", None)
        st.rerun()

    try:
        lec = sb.table("lectures").select("*").eq("id", lecture_id).single().execute()
        if not lec.data:
            st.error("المحاضرة غير موجودة")
            return
        lecture = lec.data
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    subject_id = lecture.get("subject_id")

    # ── CREDIT GATE ──────────────────────────────────────────────────
    # Check and consume 1 credit before showing any content.
    # Re-access is free (handled atomically in RPC via lecture_access_log).
    from app.services.credit_service import CreditService
    credit_svc = CreditService()

    gate_key = f"credit_granted_{lecture_id}"
    if not st.session_state.get(gate_key):
        ok, msg, data = credit_svc.consume_lecture_credit(uid, lecture_id, subject_id)
        if not ok:
            st.warning(f"🔒 {msg}")
            wallet = credit_svc.get_wallet(uid, subject_id)
            st.info(f"رصيدك الحالي: **{wallet.get('credits_available', 0)} credits**")
            if st.button("🔑 تفعيل كود جديد"):
                st.session_state.pop("active_lecture", None)
                st.session_state.student_page = "activate"
                st.rerun()
            return
        # Access granted — cache in session so next rerun doesn't re-charge
        st.session_state[gate_key] = True
        if data.get("charged"):
            wallet = credit_svc.get_wallet(uid, subject_id)
            st.success(f"✅ تم فتح المحاضرة · رصيدك: {wallet.get('credits_available', 0)} credits")
    # ── END CREDIT GATE ──────────────────────────────────────────────
    st.title(lecture["title_ar"])
    if lecture.get("description"):
        st.caption(lecture["description"])
    st.divider()

    try:
        secs = sb.table("lecture_sections").select("*")\
                 .eq("lecture_id", lecture_id)\
                 .eq("is_enabled", True)\
                 .order("order_num").execute().data or []
    except Exception as e:
        st.error(f"خطأ في تحميل الأقسام: {e}")
        return

    if not secs:
        st.info("لا توجد أقسام في هذه المحاضرة بعد.")
        return

    for sec_idx, sec in enumerate(secs):
        try:
            type_res  = sb.table("section_types").select("label_ar, icon")\
                          .eq("type_key", sec["section_type"]).single().execute()
            type_info = type_res.data or {}
            icon      = type_info.get("icon", "📄")
            label     = type_info.get("label_ar", sec["section_type"])
        except Exception:
            icon  = "📄"
            label = sec["section_type"]

        st.markdown(f"""
        <div style="border-left:4px solid #3B82F6;padding-left:16px;margin-bottom:8px">
            <span style="font-weight:700;font-size:1rem;color:#0F2D6B">{icon} {label}</span>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            render_section(sec, student_id=uid, lang=lang)

        st.divider()


# ── MY RESULTS ────────────────────────────────────────────────
def _my_results(sb, lang, uid):
    st.title("📊 " + ("نتائجي" if lang=="ar" else "My Results"))
    try:
        res = sb.table("results")\
                .select("*, exams(title, subjects(name_ar)), homework(title)")\
                .eq("student_id", uid)\
                .order("submitted_at", desc=True).execute()
        rows = res.data or []
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not rows:
        st.info("لا توجد نتائج بعد.")
        return

    scores = [r["score"]/r["total"]*100 for r in rows if r.get("total")]
    avg    = round(sum(scores)/len(scores), 1) if scores else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("📝 عدد الامتحانات", len(rows))
    c2.metric("📈 المتوسط",        f"{avg}%")
    c3.metric("🎯 المستوى", "🏆" if avg>=90 else "✅" if avg>=60 else "⚠️")
    st.divider()

    import pandas as pd
    df = pd.DataFrame([{
        "الامتحان": (r.get("exams") or {}).get("title") or (r.get("homework") or {}).get("title","—"),
        "الدرجة":   f"{r['score']}/{r['total']}",
        "%":        f"{round(r['score']/r['total']*100) if r.get('total') else 0}%",
        "التاريخ":  str(r["submitted_at"])[:10],
    } for r in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── ACTIVATE CODE ─────────────────────────────────────────────
def _activate_code(sb, lang, uid):
    st.title("🔑 تفعيل كود الوصول")
    from app.services.access_code_service import AccessCodeService
    svc = AccessCodeService()

    code_input = st.text_input("🔑 كود الوصول", placeholder="XXXXXXXX",
                                max_chars=10, key="code_input_field")
    if st.button("✅ تفعيل", key="activate_btn",
                 use_container_width=True, type="primary"):
        if not code_input.strip():
            st.error("يرجى إدخال الكود")
        else:
            with st.spinner("جاري التحقق..."):
                ok, msg, data = svc.activate_code(uid, code_input.strip().upper())
                if ok:
                    credits_added = data.get("credits_added", 1)
                    new_balance   = data.get("new_balance", "—")
                    st.success(f"🎉 {msg}")
                    st.info(f"تم إضافة **{credits_added} credits** · رصيدك الآن: **{new_balance}**")
                    st.session_state.student_page = "home"
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)

    st.divider()
    st.subheader("📚 موادك المفعّلة")
    try:
        enroll_res = sb.table("enrollments")\
                       .select("enrolled_at, subjects(name_ar)")\
                       .eq("student_id", uid).execute()
        rows = enroll_res.data or []
        if rows:
            for r in rows:
                sub_name = (r.get("subjects") or {}).get("name_ar","—")
                date     = str(r.get("enrolled_at",""))[:10]
                st.markdown(f"✅ **{sub_name}** — {date}")
        else:
            st.info("لم تنضم لأي مادة بعد.")
    except Exception:
        pass
