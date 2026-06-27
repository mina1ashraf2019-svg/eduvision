import streamlit as st
from app.core.security import get_supabase, get_current_user_id
from translations import get_lang


def show_teacher():
    lang = get_lang()
    sb   = get_supabase()
    uid  = get_current_user_id()

    with st.sidebar:
        st.markdown(f"### 📚 {'لوحة المعلم' if lang=='ar' else 'Teacher Panel'}")
        pages = {
            "subjects":       ("📚", "موادي",           "My Subjects"),
            "lectures":       ("🎬", "المحاضرات",       "Lectures"),
            "qr_attendance":  ("📱", "حضور QR",         "QR Attendance"),
            "exams":          ("📝", "الامتحانات",      "Exams"),
            "homework":       ("📋", "الواجبات",        "Homework"),
            "grading":        ("✏️", "تصحيح الواجبات", "Grading"),
            "results":        ("📈", "النتائج",          "Results"),
        }
        if "teacher_page" not in st.session_state:
            st.session_state.teacher_page = "subjects"
        for key, (icon, ar, en) in pages.items():
            label  = f"{icon} {ar if lang=='ar' else en}"
            active = st.session_state.teacher_page == key
            if st.button(label, use_container_width=True,
                         type="primary" if active else "secondary",
                         key=f"tnav_{key}"):
                st.session_state.teacher_page = key
                st.session_state.pop("active_subject", None)
                st.session_state.pop("active_lecture", None)
                st.rerun()

    page = st.session_state.teacher_page
    if   page == "subjects":      _subjects(sb, lang, uid)
    elif page == "lectures":      _lectures(sb, lang, uid)
    elif page == "qr_attendance":
        from app.pages.teacher.qr_attendance import show_qr_attendance
        show_qr_attendance()
    elif page == "exams":         _exams(sb, lang, uid)
    elif page == "homework":      _homework(sb, lang, uid)
    elif page == "grading":       _hw_grading(sb, lang, uid)
    elif page == "results":       _results(sb, lang, uid)


# ── MY SUBJECTS ───────────────────────────────────────────────
def _subjects(sb, lang, uid):
    st.title("📚 " + ("موادي" if lang=="ar" else "My Subjects"))

    try:
        res = sb.table("subject_teachers")\
                .select("subjects(id, name_ar, name_en, color_hex, grades(name_ar))")\
                .eq("teacher_id", uid).execute()
        subs = [r["subjects"] for r in (res.data or []) if r.get("subjects")]
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not subs:
        st.info("لم يتم تعيينك في أي مادة بعد. تواصل مع المشرف.")
        return

    cols = st.columns(3)
    for i, sub in enumerate(subs):
        with cols[i % 3]:
            color = sub.get("color_hex","3B82F6")
            grade = (sub.get("grades") or {}).get("name_ar","")
            st.markdown(f"""
            <div style="border-top:4px solid #{color};border-radius:10px;
                        padding:16px;background:#F8FAFC;margin-bottom:8px;
                        box-shadow:0 2px 8px rgba(0,0,0,0.06)">
                <div style="font-size:1.1rem;font-weight:700;color:#0F2D6B">
                    {sub['name_ar']}
                </div>
                <div style="color:#6B7280;font-size:0.85rem">{grade}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📂 فتح المادة", key=f"open_sub_{sub['id']}",
                         use_container_width=True):
                st.session_state.active_subject = sub["id"]
                st.session_state.teacher_page   = "lectures"
                st.rerun()


# ── LECTURES ──────────────────────────────────────────────────
def _lectures(sb, lang, uid):
    subject_id = st.session_state.get("active_subject")

    if not subject_id:
        try:
            res = sb.table("subject_teachers")\
                    .select("subjects(id, name_ar)")\
                    .eq("teacher_id", uid).execute()
            subs = [r["subjects"] for r in (res.data or []) if r.get("subjects")]
            if not subs:
                st.info("لا توجد مواد")
                return
            opts = {s["name_ar"]: s["id"] for s in subs}
            chosen = st.selectbox("اختر المادة", list(opts.keys()))
            subject_id = opts[chosen]
        except Exception as e:
            st.error(f"خطأ: {e}")
            return

    try:
        sub_res  = sb.table("subjects").select("name_ar").eq("id", subject_id).single().execute()
        sub_name = sub_res.data["name_ar"] if sub_res.data else "المادة"
    except Exception:
        sub_name = "المادة"

    st.title(f"🎬 {sub_name}")

    active_lecture = st.session_state.get("active_lecture")
    if active_lecture:
        _section_builder(sb, lang, uid, active_lecture)
        if st.button("← رجوع للمحاضرات"):
            st.session_state.pop("active_lecture", None)
            st.rerun()
        return

    with st.expander("➕ " + ("إضافة محاضرة جديدة" if lang=="ar" else "Add New Lecture")):
        with st.form("add_lecture"):
            c1, c2 = st.columns(2)
            with c1:
                l_ar   = st.text_input("عنوان المحاضرة (عربي)")
                l_en   = st.text_input("Lecture Title (English)")
            with c2:
                l_desc = st.text_area("الوصف", height=80)
                l_ord  = st.number_input("الترتيب", 1, 999, 1)
            l_pub = st.checkbox("نشر مباشرة؟", value=False)
            if st.form_submit_button("➕ إضافة", use_container_width=True):
                if l_ar:
                    sb.table("lectures").insert({
                        "subject_id":   subject_id,
                        "teacher_id":   uid,
                        "title_ar":     l_ar,
                        "title_en":     l_en or l_ar,
                        "description":  l_desc,
                        "order_num":    int(l_ord),
                        "is_published": l_pub,
                    }).execute()
                    st.success("✅ تمت إضافة المحاضرة")
                    st.rerun()

    try:
        lecs = sb.table("lectures").select("*")\
                 .eq("subject_id", subject_id)\
                 .eq("teacher_id", uid)\
                 .order("order_num").execute().data or []
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not lecs:
        st.info("لا توجد محاضرات. أضف محاضرة أولاً.")
        return

    for lec in lecs:
        pub_icon = "🟢" if lec["is_published"] else "🟡"
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        with c1:
            st.markdown(f"**{pub_icon} {lec['title_ar']}**")
        with c2:
            new_pub = st.toggle("نشر", value=bool(lec["is_published"]),
                                key=f"pub_{lec['id']}")
            if new_pub != lec["is_published"]:
                sb.table("lectures").update({"is_published": new_pub})\
                  .eq("id", lec["id"]).execute()
                st.rerun()
        with c3:
            if st.button("🧩 أقسام", key=f"sec_{lec['id']}"):
                st.session_state.active_lecture = lec["id"]
                st.rerun()
        with c4:
            if st.button("🗑️", key=f"dl_{lec['id']}"):
                sb.table("lectures").delete().eq("id", lec["id"]).execute()
                st.rerun()
        st.divider()


# ── EXAMS ─────────────────────────────────────────────────────
def _exams(sb, lang, uid):
    st.title("📝 " + ("الامتحانات" if lang=="ar" else "Exams"))

    # Get teacher's subjects
    try:
        res  = sb.table("subject_teachers")\
                 .select("subjects(id, name_ar)")\
                 .eq("teacher_id", uid).execute()
        subs = [r["subjects"] for r in (res.data or []) if r.get("subjects")]
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not subs:
        st.info("لا توجد مواد مسندة إليك.")
        return

    sub_opts = {s["name_ar"]: s["id"] for s in subs}

    with st.expander("➕ إنشاء امتحان جديد", expanded=False):
        _exam_create_form(sb, uid, sub_opts)

    # List existing exams
    try:
        sub_ids = list(sub_opts.values())
        exams   = sb.table("exams").select("*, subjects(name_ar)")\
                    .in_("subject_id", sub_ids)\
                    .order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not exams:
        st.info("لا توجد امتحانات بعد.")
        return

    st.subheader("📋 الامتحانات الحالية")
    for exam in exams:
        sub_name = (exam.get("subjects") or {}).get("name_ar", "—")
        q_count  = exam.get("questions_count", 0)
        with st.expander(f"📝 {exam['title']} | {sub_name} | {q_count} سؤال"):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**المادة:** {sub_name}")
            c2.markdown(f"**المدة:** {exam.get('duration_minutes', '—')} دقيقة")
            c3.markdown(f"**الموضوع:** {exam.get('topic', '—')}")

            # Show questions
            try:
                qs = sb.table("questions").select("*")\
                       .eq("exam_id", exam["id"])\
                       .order("order_num").execute().data or []
                if qs:
                    for qi, q in enumerate(qs, 1):
                        st.markdown(f"**{qi}. {q['question_text']}**")
                        opts = q.get("options") or []
                        correct = q.get("correct_answer", "")
                        for opt in opts:
                            icon = "✅" if opt == correct else "◦"
                            st.markdown(f"&nbsp;&nbsp;&nbsp;{icon} {opt}")
                        st.divider()
            except Exception as e:
                st.error(f"خطأ في تحميل الأسئلة: {e}")

            if st.button("🗑️ حذف الامتحان", key=f"del_exam_{exam['id']}"):
                sb.table("exams").delete().eq("id", exam["id"]).execute()
                st.success("✅ تم الحذف")
                st.rerun()


def _exam_create_form(sb, uid, sub_opts, key_prefix="main", subject_id_default=None):
    """
    Reusable exam creation form.
    Returns created exam_id if created, else None.
    Used in both the Exams page and the section builder quick-create.
    """
    import json

    with st.form(f"create_exam_{key_prefix}"):
        c1, c2 = st.columns(2)
        with c1:
            title    = st.text_input("عنوان الامتحان *")
            topic    = st.text_input("الموضوع / الوحدة")
        with c2:
            # Subject selector
            if subject_id_default and subject_id_default in sub_opts.values():
                default_label = next(k for k, v in sub_opts.items() if v == subject_id_default)
                sub_keys = list(sub_opts.keys())
                default_idx = sub_keys.index(default_label)
            else:
                default_idx = 0
            chosen_sub = st.selectbox("المادة *", list(sub_opts.keys()), index=default_idx)
            duration   = st.number_input("المدة (دقيقة) *", min_value=1, max_value=300, value=30)

        st.markdown("---")
        st.markdown("#### ✏️ الأسئلة")
        st.caption("أضف الأسئلة بتنسيق JSON أو استخدم المحرر التفاعلي أدناه")

        # Question builder — stored in session state
        q_key = f"exam_questions_{key_prefix}"
        if q_key not in st.session_state:
            st.session_state[q_key] = []

        # Show existing questions summary inside form
        if st.session_state[q_key]:
            st.success(f"✅ {len(st.session_state[q_key])} سؤال مضاف")
            for qi, q in enumerate(st.session_state[q_key], 1):
                st.markdown(f"**{qi}.** {q['question_text'][:60]}...")

        submitted = st.form_submit_button("🚀 إنشاء الامتحان", use_container_width=True)

    # Question builder OUTSIDE the form (Streamlit limitation)
    st.markdown("##### ➕ إضافة سؤال")
    with st.container():
        qc1, qc2 = st.columns([3, 1])
        with qc1:
            q_text = st.text_input("نص السؤال", key=f"qt_{key_prefix}")
        with qc2:
            q_topic = st.text_input("الموضوع", key=f"qtopic_{key_prefix}")

        opt_cols = st.columns(4)
        options = []
        opt_labels = ["أ", "ب", "ج", "د"]
        for oi, col in enumerate(opt_cols):
            with col:
                opt = st.text_input(f"خيار {opt_labels[oi]}", key=f"opt_{key_prefix}_{oi}")
                options.append(opt)

        correct_idx = st.radio(
            "الإجابة الصحيحة",
            options=[f"خيار {opt_labels[i]}" for i in range(4)],
            horizontal=True,
            key=f"correct_{key_prefix}"
        )
        correct_answer = options[["خيار أ","خيار ب","خيار ج","خيار د"].index(correct_idx)] if options else ""

        col_add, col_clear = st.columns([1, 1])
        with col_add:
            if st.button("➕ إضافة السؤال", key=f"addq_{key_prefix}"):
                if q_text and any(options):
                    st.session_state[q_key].append({
                        "question_text":  q_text,
                        "options":        [o for o in options if o],
                        "correct_answer": correct_answer,
                        "topic":          q_topic,
                        "order_num":      len(st.session_state[q_key]) + 1,
                    })
                    st.success(f"✅ تمت إضافة السؤال ({len(st.session_state[q_key])} إجمالاً)")
                    st.rerun()
                else:
                    st.error("أدخل نص السؤال وخياراً واحداً على الأقل")
        with col_clear:
            if st.button("🗑️ مسح الأسئلة", key=f"clearq_{key_prefix}"):
                st.session_state[q_key] = []
                st.rerun()

    # Handle form submission
    if submitted:
        if not title:
            st.error("أدخل عنوان الامتحان")
            return None
        if not st.session_state[q_key]:
            st.error("أضف سؤالاً واحداً على الأقل")
            return None
        try:
            subject_id = sub_opts[chosen_sub]
            # Create exam
            exam_res = sb.table("exams").insert({
                "subject_id":        subject_id,
                "teacher_id":        uid,
                "title":             title,
                "topic":             topic or None,
                "duration_minutes":  int(duration),
                "questions_count":   len(st.session_state[q_key]),
            }).execute()
            exam_id = exam_res.data[0]["id"]

            # Insert questions
            for q in st.session_state[q_key]:
                import json as _json
                sb.table("questions").insert({
                    "exam_id":        exam_id,
                    "question_text":  q["question_text"],
                    "options":        q["options"],
                    "correct_answer": q["correct_answer"],
                    "topic":          q.get("topic") or None,
                    "order_num":      q["order_num"],
                }).execute()

            st.session_state[q_key] = []
            st.success(f"✅ تم إنشاء الامتحان بنجاح! ({len(st.session_state.get(q_key, []))} سؤال)")
            st.rerun()
            return exam_id
        except Exception as e:
            st.error(f"خطأ: {e}")
            return None

    return None


# ── HOMEWORK ──────────────────────────────────────────────────
def _homework(sb, lang, uid):
    st.title("📋 " + ("الواجبات" if lang=="ar" else "Homework"))

    try:
        res  = sb.table("subject_teachers")\
                 .select("subjects(id, name_ar)")\
                 .eq("teacher_id", uid).execute()
        subs = [r["subjects"] for r in (res.data or []) if r.get("subjects")]
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not subs:
        st.info("لا توجد مواد مسندة إليك.")
        return

    sub_opts = {s["name_ar"]: s["id"] for s in subs}

    with st.expander("➕ إنشاء واجب جديد", expanded=False):
        _homework_create_form(sb, uid, sub_opts)

    # List existing homework
    try:
        sub_ids = list(sub_opts.values())
        hws     = sb.table("homework").select("*, subjects(name_ar)")\
                    .in_("subject_id", sub_ids)\
                    .order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not hws:
        st.info("لا توجد واجبات بعد.")
        return

    st.subheader("📋 الواجبات الحالية")
    for hw in hws:
        sub_name = (hw.get("subjects") or {}).get("name_ar", "—")
        deadline = str(hw.get("deadline","—"))[:10] if hw.get("deadline") else "بدون موعد"
        with st.expander(f"📋 {hw['title']} | {sub_name} | ⏰ {deadline}"):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**المادة:** {sub_name}")
            c2.markdown(f"**الموعد النهائي:** {deadline}")
            c3.markdown(f"**رفع ملف:** {'✅' if hw.get('allow_file_upload') else '❌'}")

            # Questions
            try:
                qs = sb.table("questions").select("*")\
                       .eq("hw_id", hw["id"])\
                       .order("order_num").execute().data or []
                if qs:
                    for qi, q in enumerate(qs, 1):
                        st.markdown(f"**{qi}. {q['question_text']}**")
                        opts = q.get("options") or []
                        correct = q.get("correct_answer","")
                        for opt in opts:
                            icon = "✅" if opt == correct else "◦"
                            st.markdown(f"&nbsp;&nbsp;&nbsp;{icon} {opt}")
                        st.divider()
            except Exception as e:
                st.error(f"خطأ: {e}")

            if st.button("🗑️ حذف الواجب", key=f"del_hw_{hw['id']}"):
                sb.table("homework").delete().eq("id", hw["id"]).execute()
                st.success("✅ تم الحذف")
                st.rerun()


def _homework_create_form(sb, uid, sub_opts, key_prefix="main", subject_id_default=None):
    """
    Reusable homework creation form.
    Returns created hw_id if created, else None.
    """
    with st.form(f"create_hw_{key_prefix}"):
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("عنوان الواجب *")
            topic = st.text_input("الموضوع / الوحدة")
        with c2:
            if subject_id_default and subject_id_default in sub_opts.values():
                default_label = next(k for k, v in sub_opts.items() if v == subject_id_default)
                default_idx   = list(sub_opts.keys()).index(default_label)
            else:
                default_idx = 0
            chosen_sub       = st.selectbox("المادة *", list(sub_opts.keys()), index=default_idx)
            deadline         = st.date_input("الموعد النهائي (اختياري)", value=None)

        allow_upload = st.checkbox("السماح برفع ملف (hw_upload)")
        st.markdown("---")
        st.markdown("#### ✏️ الأسئلة (MCQ اختياري)")

        q_key = f"hw_questions_{key_prefix}"
        if q_key not in st.session_state:
            st.session_state[q_key] = []

        if st.session_state[q_key]:
            st.success(f"✅ {len(st.session_state[q_key])} سؤال مضاف")
            for qi, q in enumerate(st.session_state[q_key], 1):
                st.markdown(f"**{qi}.** {q['question_text'][:60]}...")

        submitted = st.form_submit_button("🚀 إنشاء الواجب", use_container_width=True)

    # Question builder outside form
    st.markdown("##### ➕ إضافة سؤال للواجب")
    with st.container():
        qc1, qc2 = st.columns([3, 1])
        with qc1:
            q_text  = st.text_input("نص السؤال", key=f"hwqt_{key_prefix}")
        with qc2:
            q_topic = st.text_input("الموضوع", key=f"hwqtopic_{key_prefix}")

        opt_cols = st.columns(4)
        options  = []
        opt_labels = ["أ","ب","ج","د"]
        for oi, col in enumerate(opt_cols):
            with col:
                opt = st.text_input(f"خيار {opt_labels[oi]}", key=f"hwopt_{key_prefix}_{oi}")
                options.append(opt)

        correct_idx = st.radio(
            "الإجابة الصحيحة",
            options=[f"خيار {opt_labels[i]}" for i in range(4)],
            horizontal=True,
            key=f"hwcorrect_{key_prefix}"
        )
        correct_answer = options[["خيار أ","خيار ب","خيار ج","خيار د"].index(correct_idx)] if options else ""

        col_add, col_clear = st.columns([1, 1])
        with col_add:
            if st.button("➕ إضافة السؤال", key=f"hwaddq_{key_prefix}"):
                if q_text and any(options):
                    st.session_state[q_key].append({
                        "question_text":  q_text,
                        "options":        [o for o in options if o],
                        "correct_answer": correct_answer,
                        "topic":          q_topic,
                        "order_num":      len(st.session_state[q_key]) + 1,
                    })
                    st.success(f"✅ تمت إضافة السؤال ({len(st.session_state[q_key])} إجمالاً)")
                    st.rerun()
                else:
                    st.error("أدخل نص السؤال وخياراً واحداً على الأقل")
        with col_clear:
            if st.button("🗑️ مسح الأسئلة", key=f"hwclearq_{key_prefix}"):
                st.session_state[q_key] = []
                st.rerun()

    if submitted:
        if not title:
            st.error("أدخل عنوان الواجب")
            return None
        try:
            subject_id = sub_opts[chosen_sub]
            hw_res = sb.table("homework").insert({
                "subject_id":        subject_id,
                "teacher_id":        uid,
                "title":             title,
                "topic":             topic or None,
                "deadline":          str(deadline) if deadline else None,
                "allow_file_upload": allow_upload,
                "questions_count":   len(st.session_state[q_key]),
            }).execute()
            hw_id = hw_res.data[0]["id"]

            for q in st.session_state[q_key]:
                sb.table("questions").insert({
                    "hw_id":          hw_id,
                    "question_text":  q["question_text"],
                    "options":        q["options"],
                    "correct_answer": q["correct_answer"],
                    "topic":          q.get("topic") or None,
                    "order_num":      q["order_num"],
                }).execute()

            st.session_state[q_key] = []
            st.success(f"✅ تم إنشاء الواجب بنجاح!")
            st.rerun()
            return hw_id
        except Exception as e:
            st.error(f"خطأ: {e}")
            return None

    return None


# ── SECTION BUILDER ───────────────────────────────────────────
def _section_builder(sb, lang, uid, lecture_id):
    try:
        lec = sb.table("lectures").select("title_ar, subject_id").eq("id", lecture_id).single().execute()
        lec_title  = lec.data["title_ar"] if lec.data else "المحاضرة"
        subject_id = lec.data["subject_id"] if lec.data else None
    except Exception:
        lec_title  = "المحاضرة"
        subject_id = None

    st.subheader(f"🧩 أقسام: {lec_title}")

    try:
        types_res = sb.table("section_types").select("*").eq("is_active", True).execute()
        types     = types_res.data or []
        type_opts = {f"{t['icon']} {t['label_ar']}": t["type_key"] for t in types}
    except Exception:
        types     = []
        type_opts = {}

    if type_opts:
        c1, c2 = st.columns([4, 1])
        with c1:
            chosen_type_label = st.selectbox("نوع القسم", list(type_opts.keys()),
                                              key="new_sec_type")
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ إضافة قسم", use_container_width=True):
                type_key = type_opts[chosen_type_label]
                secs_res = sb.table("lecture_sections").select("order_num")\
                             .eq("lecture_id", lecture_id).execute()
                max_ord  = max((s["order_num"] for s in (secs_res.data or [])), default=0)
                sb.table("lecture_sections").insert({
                    "lecture_id":   lecture_id,
                    "section_type": type_key,
                    "order_num":    max_ord + 1,
                    "is_enabled":   True,
                    "config_json":  "{}",
                }).execute()
                st.rerun()

    st.divider()

    try:
        secs = sb.table("lecture_sections").select("*")\
                 .eq("lecture_id", lecture_id)\
                 .order("order_num").execute().data or []
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not secs:
        st.info("لا توجد أقسام بعد. اختر نوع القسم وأضفه.")
        return

    for i, sec in enumerate(secs):
        type_info = next((t for t in types if t["type_key"] == sec["section_type"]), {})
        icon      = type_info.get("icon", "📄")
        label     = type_info.get("label_ar", sec["section_type"])

        c1, c2, c3, c4, c5 = st.columns([1, 5, 1, 1, 1])

        with c1:
            if i > 0 and st.button("⬆️", key=f"up_{sec['id']}"):
                prev = secs[i-1]
                sb.table("lecture_sections").update({"order_num": prev["order_num"]})\
                  .eq("id", sec["id"]).execute()
                sb.table("lecture_sections").update({"order_num": sec["order_num"]})\
                  .eq("id", prev["id"]).execute()
                st.rerun()
            if i < len(secs)-1 and st.button("⬇️", key=f"dn_{sec['id']}"):
                nxt = secs[i+1]
                sb.table("lecture_sections").update({"order_num": nxt["order_num"]})\
                  .eq("id", sec["id"]).execute()
                sb.table("lecture_sections").update({"order_num": sec["order_num"]})\
                  .eq("id", nxt["id"]).execute()
                st.rerun()

        with c2:
            with st.expander(f"{icon} {label}"):
                _section_config_form(sb, sec, lang, uid, subject_id)

        with c3:
            enabled = st.toggle("", value=bool(sec["is_enabled"]),
                                key=f"en_{sec['id']}")
            if enabled != bool(sec["is_enabled"]):
                sb.table("lecture_sections")\
                  .update({"is_enabled": enabled})\
                  .eq("id", sec["id"]).execute()
                st.rerun()

        with c5:
            if st.button("🗑️", key=f"del_{sec['id']}"):
                sb.table("lecture_sections").delete().eq("id", sec["id"]).execute()
                st.rerun()


def _section_config_form(sb, sec, lang, uid=None, subject_id=None):
    """Per-section-type config form with quick-create for exam/homework."""
    import json
    from app.schemas.section_configs import validate_section_config

    section_type = sec["section_type"]
    try:
        config = json.loads(sec.get("config_json") or "{}")
    except Exception:
        config = {}

    new_config = {}

    if section_type in ("video", "hw_review_video"):
        from app.sections.video import render_youtube_url_input
        yt = render_youtube_url_input(current_url=config.get("youtube_url",""), key=f"yt_url_{sec['id']}_{section_type}")
        new_config = {"youtube_url": yt or None}

    elif section_type == "quiz":
        try:
            if not subject_id:
                lec_res  = sb.table("lectures").select("subject_id").eq("id", sec["lecture_id"]).single().execute()
                subject_id = lec_res.data["subject_id"] if lec_res.data else None

            exams  = sb.table("exams").select("id, title").eq("subject_id", subject_id).execute().data or []
            e_opts = {e["title"]: e["id"] for e in exams}

            if e_opts:
                cur_exam  = config.get("exam_id","")
                cur_label = next((k for k,v in e_opts.items() if v==cur_exam), list(e_opts.keys())[0])
                chosen_e  = st.selectbox("اختر الامتحان", list(e_opts.keys()),
                                         index=list(e_opts.keys()).index(cur_label),
                                         key=f"exam_{sec['id']}")
                dur = st.number_input("المدة (دقيقة)", 1, 240,
                                      value=config.get("duration_minutes",30),
                                      key=f"dur_{sec['id']}")
                new_config = {"exam_id": e_opts[chosen_e], "duration_minutes": int(dur)}
            else:
                st.warning("لا توجد امتحانات. أنشئ امتحاناً أولاً من صفحة الامتحانات.")
                new_config = config

            # Quick-create shortcut
            if uid and subject_id:
                with st.expander("➕ إنشاء امتحان جديد من هنا"):
                    sub_res  = sb.table("subjects").select("name_ar").eq("id", subject_id).single().execute()
                    sub_name = sub_res.data["name_ar"] if sub_res.data else "المادة"
                    _exam_create_form(sb, uid, {sub_name: subject_id},
                                      key_prefix=f"quick_{sec['id']}",
                                      subject_id_default=subject_id)

        except Exception as e:
            st.error(f"خطأ: {e}")
            return

    elif section_type == "homework":
        try:
            if not subject_id:
                lec_res  = sb.table("lectures").select("subject_id").eq("id", sec["lecture_id"]).single().execute()
                subject_id = lec_res.data["subject_id"] if lec_res.data else None

            hws    = sb.table("homework").select("id, title").eq("subject_id", subject_id).execute().data or []
            h_opts = {h["title"]: h["id"] for h in hws}

            if h_opts:
                cur_hw    = config.get("hw_id","")
                cur_label = next((k for k,v in h_opts.items() if v==cur_hw), list(h_opts.keys())[0])
                chosen_h  = st.selectbox("اختر الواجب", list(h_opts.keys()),
                                         index=list(h_opts.keys()).index(cur_label),
                                         key=f"hw_{sec['id']}")
                new_config = {"hw_id": h_opts[chosen_h]}
            else:
                st.warning("لا توجد واجبات. أنشئ واجباً أولاً من صفحة الواجبات.")
                new_config = config

            # Quick-create shortcut
            if uid and subject_id:
                with st.expander("➕ إنشاء واجب جديد من هنا"):
                    sub_res  = sb.table("subjects").select("name_ar").eq("id", subject_id).single().execute()
                    sub_name = sub_res.data["name_ar"] if sub_res.data else "المادة"
                    _homework_create_form(sb, uid, {sub_name: subject_id},
                                          key_prefix=f"quickhw_{sec['id']}",
                                          subject_id_default=subject_id)

        except Exception as e:
            st.error(f"خطأ: {e}")
            return

    elif section_type == "pdf_notes":
        title  = st.text_input("عنوان الـ PDF", value=config.get("title",""),
                               key=f"pdft_{sec['id']}")
        allow  = st.checkbox("السماح بالتنزيل",
                             value=config.get("allow_download", True),
                             key=f"pdfd_{sec['id']}")
        uploaded = st.file_uploader("ارفع ملف PDF", type=["pdf"],
                                    key=f"pdfup_{sec['id']}")
        file_path = config.get("file_path","")
        if uploaded:
            st.info("سيتم الرفع عند الحفظ (يتطلب Supabase Storage)")
        new_config = {"file_path": file_path, "title": title,
                      "allow_download": allow, "bucket": "notes"}

    elif section_type == "links":
        st.caption("أضف الروابط الخارجية")
        links = config.get("links", [])
        updated_links = []
        for j, lnk in enumerate(links):
            c1, c2, c3 = st.columns([3, 3, 1])
            with c1:
                lbl = st.text_input("العنوان", value=lnk.get("label",""),
                                    key=f"ll_{sec['id']}_{j}")
            with c2:
                url = st.text_input("الرابط", value=lnk.get("url",""),
                                    key=f"lu_{sec['id']}_{j}")
            with c3:
                st.markdown("<br>", unsafe_allow_html=True)
                if not st.button("🗑️", key=f"lx_{sec['id']}_{j}"):
                    updated_links.append({"label": lbl, "url": url})
        if st.button("➕ رابط جديد", key=f"ladd_{sec['id']}"):
            updated_links.append({"label": "", "url": ""})
        new_config = {"links": updated_links}

    elif section_type == "discussion":
        prompt = st.text_area("سؤال النقاش (اختياري)",
                              value=config.get("prompt",""),
                              key=f"disc_{sec['id']}")
        anon   = st.checkbox("السماح بالنشر مجهول الهوية",
                             value=config.get("allow_anonymous", False),
                             key=f"anon_{sec['id']}")
        new_config = {"prompt": prompt, "allow_anonymous": anon}

    else:
        st.caption(f"نوع القسم: `{section_type}` — لا توجد إعدادات إضافية")
        new_config = config

    if st.button("💾 حفظ الإعدادات", key=f"save_{sec['id']}"):
        try:
            validated = validate_section_config(section_type, new_config)
            sb.table("lecture_sections")\
              .update({"config_json": json.dumps(validated)})\
              .eq("id", sec["id"]).execute()
            st.success("✅ تم الحفظ")
            st.rerun()
        except Exception as e:
            st.error(f"خطأ في الإعدادات: {e}")


# ── RESULTS ───────────────────────────────────────────────────
def _results(sb, lang, uid):
    st.title("📈 " + ("نتائج طلابي" if lang=="ar" else "My Students' Results"))
    try:
        subs_res = sb.table("subject_teachers").select("subject_id")\
                     .eq("teacher_id", uid).execute()
        sub_ids  = [r["subject_id"] for r in (subs_res.data or [])]
        if not sub_ids:
            st.info("لا توجد مواد مسندة إليك.")
            return

        res = sb.table("results")\
                .select("*, profiles(full_name), exams(title, subject_id)")\
                .order("submitted_at", desc=True).limit(200).execute()

        rows = [r for r in (res.data or [])
                if (r.get("exams") or {}).get("subject_id") in sub_ids]

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
            st.info("لا توجد نتائج بعد")
    except Exception as e:
        st.error(f"خطأ: {e}")


# ── HW GRADING ────────────────────────────────────────────────
def _hw_grading(sb, lang, uid):
    st.title("✏️ " + ("تصحيح الواجبات" if lang=="ar" else "Homework Grading"))

    # Get teacher's subjects
    try:
        res  = sb.table("subject_teachers")\
                 .select("subjects(id, name_ar)")\
                 .eq("teacher_id", uid).execute()
        subs = [r["subjects"] for r in (res.data or []) if r.get("subjects")]
    except Exception as e:
        st.error(f"خطأ: {e}")
        return

    if not subs:
        st.info("لا توجد مواد مسندة إليك.")
        return

    sub_opts = {s["name_ar"]: s["id"] for s in subs}

    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        chosen_sub = st.selectbox("المادة", ["الكل"] + list(sub_opts.keys()), key="grade_sub")
    with c2:
        status_filter = st.selectbox("الحالة", ["الكل", "بانتظار التصحيح", "تم التصحيح"], key="grade_status")
    with c3:
        search_name = st.text_input("🔍 بحث باسم الطالب", key="grade_search")

    st.divider()

    try:
        # Get hw_uploads for teacher's subjects via lecture_sections → lectures → subjects
        sub_ids = list(sub_opts.values()) if chosen_sub == "الكل" else [sub_opts[chosen_sub]]

        # Get all sections of type homework/hw_upload belonging to teacher's subjects
        lecs_res = sb.table("lectures").select("id").in_("subject_id", sub_ids)\
                     .eq("teacher_id", uid).execute()
        lec_ids  = [l["id"] for l in (lecs_res.data or [])]

        if not lec_ids:
            st.info("لا توجد محاضرات بعد.")
            return

        secs_res = sb.table("lecture_sections").select("id, lecture_id, config_json")\
                     .in_("lecture_id", lec_ids)\
                     .in_("section_type", ["hw_upload", "homework"])\
                     .execute()
        sec_ids = [s["id"] for s in (secs_res.data or [])]

        if not sec_ids:
            st.info("لا توجد أقسام رفع واجبات بعد.")
            return

        # Get uploads
        uploads_res = sb.table("hw_uploads")\
                        .select("*, profiles(full_name), lecture_sections(lecture_id)")\
                        .in_("section_id", sec_ids)\
                        .order("uploaded_at", desc=True)\
                        .execute()
        uploads = uploads_res.data or []

    except Exception as e:
        st.error(f"خطأ في تحميل الواجبات: {e}")
        return

    # Apply filters
    if status_filter == "بانتظار التصحيح":
        uploads = [u for u in uploads if u.get("grade") is None]
    elif status_filter == "تم التصحيح":
        uploads = [u for u in uploads if u.get("grade") is not None]

    if search_name:
        uploads = [u for u in uploads
                   if search_name.lower() in ((u.get("profiles") or {}).get("full_name","")).lower()]

    if not uploads:
        st.info("لا توجد واجبات مرفوعة تطابق الفلتر.")
        return

    # Summary metrics
    total     = len(uploads)
    graded    = sum(1 for u in uploads if u.get("grade") is not None)
    pending   = total - graded

    m1, m2, m3 = st.columns(3)
    m1.metric("📥 إجمالي المرفوعة", total)
    m2.metric("⏳ بانتظار التصحيح", pending)
    m3.metric("✅ تم تصحيحها",      graded)

    st.divider()

    # Grading cards
    for upload in uploads:
        student_name = (upload.get("profiles") or {}).get("full_name", "—")
        file_name    = upload.get("file_name", "—")
        file_path    = upload.get("file_path", "")
        uploaded_at  = str(upload.get("uploaded_at",""))[:19]
        grade        = upload.get("grade")
        feedback     = upload.get("feedback", "")
        upload_id    = upload["id"]
        is_graded    = grade is not None

        status_badge = "✅ تم التصحيح" if is_graded else "⏳ بانتظار"
        with st.expander(
            f"{status_badge} | 👤 {student_name} | 📎 {file_name} | 🕒 {uploaded_at}",
            expanded=not is_graded
        ):
            col_file, col_grade = st.columns([3, 2])

            with col_file:
                st.markdown(f"**الطالب:** {student_name}")
                st.markdown(f"**الملف:** `{file_name}`")
                st.caption(f"رُفع في: {uploaded_at}")

                # Download link
                if file_path:
                    try:
                        from app.core.security import get_supabase
                        sb2 = get_supabase()
                        signed = sb2.storage.from_("hw_uploads").create_signed_url(file_path, 3600)
                        dl_url = signed.get("signedURL") or signed.get("signed_url", "")
                        if dl_url:
                            st.markdown(f"""
                            <a href="{dl_url}" target="_blank"
                               style="display:inline-block;padding:6px 16px;
                                      background:#2563EB;color:white;border-radius:6px;
                                      text-decoration:none;font-weight:600;font-size:0.9rem">
                                ⬇️ تحميل الملف
                            </a>
                            """, unsafe_allow_html=True)
                    except Exception:
                        st.caption("تعذّر إنشاء رابط التحميل")

            with col_grade:
                st.markdown("**التصحيح:**")

                new_grade = st.number_input(
                    "الدرجة",
                    min_value=0, max_value=100,
                    value=int(grade) if grade is not None else 0,
                    step=1,
                    key=f"grade_input_{upload_id}"
                )
                new_feedback = st.text_area(
                    "ملاحظات / تغذية راجعة",
                    value=feedback or "",
                    height=80,
                    key=f"feedback_input_{upload_id}",
                    placeholder="اكتب ملاحظاتك للطالب هنا..."
                )

                btn_label = "🔄 تحديث التصحيح" if is_graded else "💾 حفظ التصحيح"
                if st.button(btn_label, key=f"save_grade_{upload_id}", type="primary"):
                    try:
                        sb.table("hw_uploads").update({
                            "grade":    new_grade,
                            "feedback": new_feedback,
                            "graded_by": uid,
                            "graded_at": "now()",
                        }).eq("id", upload_id).execute()
                        st.success(f"✅ تم حفظ الدرجة: {new_grade}/100")
                        st.rerun()
                    except Exception as e:
                        st.error(f"خطأ: {e}")
