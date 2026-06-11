import streamlit as st
from app.core.security import get_supabase, get_current_user_id
from app.services.progress_service import ProgressService
from app.sections import render_section
from translations import get_lang


def show_student():
    lang  = get_lang()
    sb    = get_supabase()
    uid   = get_current_user_id()
    prog  = ProgressService()

    # Navigation state
    active_subject = st.session_state.get("active_subject")
    active_lecture = st.session_state.get("active_lecture")

    with st.sidebar:
        st.markdown(f"### 🎓 {'لوحة الطالب' if lang=='ar' else 'Student Panel'}")
        if st.button("🏠 " + ("الرئيسية" if lang=="ar" else "Home"),
                     use_container_width=True):
            st.session_state.pop("active_subject", None)
            st.session_state.pop("active_lecture", None)
            st.rerun()
        if st.button("📊 " + ("نتائجي" if lang=="ar" else "My Results"),
                     use_container_width=True):
            st.session_state.student_page = "results"
            st.session_state.pop("active_subject", None)
            st.session_state.pop("active_lecture", None)
            st.rerun()
        if st.button("🔑 " + ("تفعيل كود" if lang=="ar" else "Activate Code"),
                     use_container_width=True):
            st.session_state.student_page = "activate"
            st.session_state.pop("active_subject", None)
            st.session_state.pop("active_lecture", None)
            st.rerun()

    student_page = st.session_state.get("student_page", "home")

    if student_page == "results":
        _my_results(sb, lang, uid)
    elif student_page == "activate":
        _activate_code(sb, lang, uid)
    elif active_lecture:
        _lecture_view(sb, lang, uid, active_lecture, prog)
    elif active_subject:
        _subject_view(sb, lang, uid, active_subject, prog)
    else:
        _dashboard(sb, lang, uid, prog)
        st.session_state.student_page = "home"


# ══════════════════════════════════════════════════════════════
# DASHBOARD — Subject Cards
# ══════════════════════════════════════════════════════════════
def _dashboard(sb, lang, uid, prog):
    user = st.session_state.user
    st.title(f"👋 {'أهلاً' if lang=='ar' else 'Welcome'}, {user['full_name']}!")

    # Enrolled subjects
    try:
        enroll_res = sb.table("enrollments")\
                       .select("subject_id, subjects(id, name_ar, name_en, color_hex, grades(name_ar))")\
                       .eq("student_id", uid).execute()
        enrolled = [r["subjects"] for r in (enroll_res.data or []) if r.get("subjects")]
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not enrolled:
        st.info("🔒 لم تنضم لأي مادة بعد. استخدم كود الوصول للانضمام.")
        _activate_code(sb, lang, uid)
        return

    st.subheader("📚 " + ("موادي" if lang=="ar" else "My Subjects"))
    cols = st.columns(3)
    for i, sub in enumerate(enrolled):
        subject_prog = prog.get_subject_progress(uid, sub["id"])
        color   = sub.get("color_hex","3B82F6")
        grade   = (sub.get("grades") or {}).get("name_ar","")
        with cols[i % 3]:
            st.markdown(f"""
            <div style="border-top:5px solid #{color};border-radius:12px;
                        padding:20px 16px 12px;background:#F8FAFC;
                        box-shadow:0 2px 10px rgba(0,0,0,0.07);margin-bottom:4px">
                <div style="font-size:1.15rem;font-weight:800;color:#0F2D6B;margin-bottom:4px">
                    {sub['name_ar']}
                </div>
                <div style="color:#6B7280;font-size:0.82rem;margin-bottom:10px">{grade}</div>
                <div style="background:#E2E8F0;border-radius:99px;height:6px;margin-bottom:6px">
                    <div style="background:#{color};width:{subject_prog}%;height:6px;border-radius:99px"></div>
                </div>
                <div style="color:#6B7280;font-size:0.78rem">{subject_prog}% مكتمل</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📖 فتح", key=f"open_{sub['id']}", use_container_width=True):
                st.session_state.active_subject = sub["id"]
                st.session_state.student_page   = "home"
                st.rerun()


# ══════════════════════════════════════════════════════════════
# SUBJECT VIEW — Teacher list
# ══════════════════════════════════════════════════════════════
def _subject_view(sb, lang, uid, subject_id, prog):
    try:
        sub = sb.table("subjects").select("name_ar, name_en").eq("id",subject_id).single().execute()
        sub_name = sub.data["name_ar"] if sub.data else "المادة"
    except Exception:
        sub_name = "المادة"

    st.title(f"📚 {sub_name}")
    if st.button("← " + ("رجوع" if lang=="ar" else "Back")):
        st.session_state.pop("active_subject", None)
        st.rerun()
    st.divider()

    # Teachers in this subject
    try:
        t_res    = sb.table("subject_teachers")\
                     .select("teacher_id, display_order, profiles(id, full_name, bio, avatar_url)")\
                     .eq("subject_id", subject_id)\
                     .order("display_order").execute()
        teachers = [r["profiles"] for r in (t_res.data or []) if r.get("profiles")]
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not teachers:
        st.info("لم يتم تعيين معلمين بعد.")
        return

    st.subheader("👨‍🏫 " + ("المعلمون" if lang=="ar" else "Teachers"))
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
            initials = teacher["full_name"][0].upper() if teacher["full_name"] else "?"
            st.markdown(f"""
            <div style="text-align:center;padding:24px 16px;border-radius:12px;
                        border:1.5px solid #E2E8F0;background:#fff;margin-bottom:8px">
                <div style="width:64px;height:64px;border-radius:50%;background:#3B82F6;
                            display:flex;align-items:center;justify-content:center;
                            font-size:1.8rem;font-weight:900;color:white;margin:0 auto 10px">
                    {initials}
                </div>
                <div style="font-weight:700;font-size:1rem;color:#0F2D6B">{teacher['full_name']}</div>
                <div style="color:#6B7280;font-size:0.82rem;margin-top:4px">
                    {teacher.get('bio','') or ''}
                </div>
                <div style="color:#3B82F6;font-size:0.82rem;margin-top:8px">
                    📖 {lec_count} {'محاضرة' if lang=='ar' else 'lectures'}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("عرض المحاضرات", key=f"view_t_{teacher['id']}",
                         use_container_width=True):
                st.session_state.active_teacher = teacher["id"]
                st.session_state.view_lecture_list = True
                st.rerun()

    # Lecture list (if teacher selected)
    if st.session_state.get("view_lecture_list") and st.session_state.get("active_teacher"):
        _lecture_list(sb, lang, uid, subject_id,
                      st.session_state.active_teacher, prog)


# ══════════════════════════════════════════════════════════════
# LECTURE LIST
# ══════════════════════════════════════════════════════════════
def _lecture_list(sb, lang, uid, subject_id, teacher_id, prog):
    st.divider()
    st.subheader("🎬 " + ("المحاضرات" if lang=="ar" else "Lectures"))

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

    for lec in lecs:
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
            if st.button("▶️ فتح", key=f"lec_{lec['id']}", use_container_width=True):
                st.session_state.active_lecture = lec["id"]
                st.rerun()
        st.divider()


# ══════════════════════════════════════════════════════════════
# LECTURE VIEW — Section Renderer
# ══════════════════════════════════════════════════════════════
def _lecture_view(sb, lang, uid, lecture_id, prog):
    if st.button("← " + ("رجوع" if lang=="ar" else "Back")):
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

    st.title(lecture["title_ar"])
    if lecture.get("description"):
        st.caption(lecture["description"])

    # Update last viewed
    prog.mark_section_complete.__func__ if False else None
    try:
        sb.table("student_progress").upsert({
            "student_id":   uid,
            "lecture_id":   lecture_id,
            "subject_id":   lecture["subject_id"],
            "last_viewed":  __import__("datetime").datetime.utcnow().isoformat(),
        }, on_conflict="student_id,lecture_id").execute()
    except Exception:
        pass

    st.divider()

    # Load sections
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

    # Render each section
    for sec in secs:
        try:
            type_res  = sb.table("section_types").select("label_ar, label_en, icon")\
                          .eq("type_key", sec["section_type"]).single().execute()
            type_info = type_res.data or {}
            icon      = type_info.get("icon","📄")
            label     = type_info.get("label_ar" if lang=="ar" else "label_en",
                                      sec["section_type"])
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


# ══════════════════════════════════════════════════════════════
# MY RESULTS
# ══════════════════════════════════════════════════════════════
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

    # Summary metrics
    scores = [r["score"]/r["total"]*100 for r in rows if r["total"]]
    avg    = round(sum(scores)/len(scores), 1) if scores else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("📝 عدد الامتحانات", len(rows))
    c2.metric("📈 المتوسط العام",  f"{avg}%")
    level = "🏆 ممتاز" if avg>=90 else "✅ جيد جداً" if avg>=80 else "📚 جيد" if avg>=60 else "⚠️ يحتاج تحسين"
    c3.metric("🎯 المستوى", level)

    st.divider()

    import pandas as pd
    df_rows = []
    for r in rows:
        pct   = round(r["score"]/r["total"]*100) if r["total"] else 0
        grade = "A" if pct>=90 else "B" if pct>=80 else "C" if pct>=70 else "D" if pct>=60 else "F"
        title = (r.get("exams") or {}).get("title") or (r.get("homework") or {}).get("title","—")
        sub   = ((r.get("exams") or {}).get("subjects") or {}).get("name_ar","—")
        df_rows.append({
            "الامتحان / الواجب": title,
            "المادة":    sub,
            "الدرجة":    f"{r['score']}/{r['total']}",
            "%":         f"{pct}%",
            "التقدير":   grade,
            "التاريخ":   str(r["submitted_at"])[:10],
        })
    st.dataframe(pd.DataFrame(df_rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# ACTIVATE ACCESS CODE
# ══════════════════════════════════════════════════════════════
def _activate_code(sb, lang, uid):
    st.title("🔑 " + ("تفعيل كود الوصول" if lang=="ar" else "Activate Access Code"))
    st.markdown(
        "أدخل كود الوصول الذي حصلت عليه للانضمام إلى المادة."
        if lang=="ar" else
        "Enter your access code to join a subject."
    )

    from app.services.access_code_service import AccessCodeService
    svc = AccessCodeService()

    code_input = st.text_input(
        "🔑 " + ("كود الوصول" if lang=="ar" else "Access Code"),
        placeholder="XXXXXXXX",
        max_chars=10,
    )

    if st.button("✅ " + ("تفعيل الكود" if lang=="ar" else "Activate"),
                 use_container_width=True, type="primary"):
        if not code_input.strip():
            st.error("يرجى إدخال الكود")
        else:
            with st.spinner("جاري التحقق..."):
                ok, msg = svc.activate_code(uid, code_input.strip().upper())
                if ok:
                    st.success(msg)
                    st.session_state.student_page = "home"
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)

    # Already enrolled subjects
    st.divider()
    st.subheader("📚 " + ("موادك المفعّلة" if lang=="ar" else "Your Active Subjects"))
    try:
        enroll_res = sb.table("enrollments")\
                       .select("enrolled_at, subjects(name_ar)")\
                       .eq("student_id", uid).execute()
        rows = enroll_res.data or []
        if rows:
            for r in rows:
                sub_name = (r.get("subjects") or {}).get("name_ar","—")
                date     = str(r.get("enrolled_at",""))[:10]
                st.markdown(f"✅ **{sub_name}** — انضممت في {date}")
        else:
            st.info("لم تنضم لأي مادة بعد.")
    except Exception:
        pass
