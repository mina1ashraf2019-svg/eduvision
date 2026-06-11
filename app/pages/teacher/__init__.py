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
            "subjects":  ("📚", "موادي",         "My Subjects"),
            "lectures":  ("🎬", "المحاضرات",     "Lectures"),
            "results":   ("📈", "النتائج",        "Results"),
        }
        if "teacher_page" not in st.session_state:
            st.session_state.teacher_page = "subjects"
        for key, (icon, ar, en) in pages.items():
            label  = f"{icon} {ar if lang=='ar' else en}"
            active = st.session_state.teacher_page == key
            if st.button(label, use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.teacher_page = key
                st.session_state.pop("active_subject", None)
                st.session_state.pop("active_lecture", None)
                st.rerun()

    page = st.session_state.teacher_page
    if   page == "subjects": _subjects(sb, lang, uid)
    elif page == "lectures": _lectures(sb, lang, uid)
    elif page == "results":  _results(sb, lang, uid)


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

    # Subject selector if not set
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

    # Get subject name
    try:
        sub_res = sb.table("subjects").select("name_ar").eq("id", subject_id).single().execute()
        sub_name = sub_res.data["name_ar"] if sub_res.data else "المادة"
    except Exception:
        sub_name = "المادة"

    st.title(f"🎬 {sub_name}")

    # Active lecture → section builder
    active_lecture = st.session_state.get("active_lecture")
    if active_lecture:
        _section_builder(sb, lang, uid, active_lecture)
        if st.button("← رجوع للمحاضرات"):
            st.session_state.pop("active_lecture", None)
            st.rerun()
        return

    # Add lecture
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

    # Lecture list
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
            # Toggle publish
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


# ── SECTION BUILDER ───────────────────────────────────────────
def _section_builder(sb, lang, uid, lecture_id):
    try:
        lec = sb.table("lectures").select("title_ar").eq("id", lecture_id).single().execute()
        lec_title = lec.data["title_ar"] if lec.data else "المحاضرة"
    except Exception:
        lec_title = "المحاضرة"

    st.subheader(f"🧩 أقسام: {lec_title}")

    # Section types
    try:
        types_res = sb.table("section_types").select("*").eq("is_active", True).execute()
        types     = types_res.data or []
        type_opts = {f"{t['icon']} {t['label_ar']}": t["type_key"] for t in types}
    except Exception:
        types     = []
        type_opts = {}

    # Add section
    if type_opts:
        c1, c2 = st.columns([4, 1])
        with c1:
            chosen_type_label = st.selectbox("نوع القسم", list(type_opts.keys()),
                                              key="new_sec_type")
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ إضافة قسم", use_container_width=True):
                type_key = type_opts[chosen_type_label]
                # Get max order
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

    # Existing sections
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
        # Find label for this type
        type_info = next((t for t in types if t["type_key"] == sec["section_type"]), {})
        icon      = type_info.get("icon", "📄")
        label     = type_info.get("label_ar", sec["section_type"])

        c1, c2, c3, c4, c5 = st.columns([1, 5, 1, 1, 1])

        # Reorder
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

        # Config expander
        with c2:
            with st.expander(f"{icon} {label}"):
                _section_config_form(sb, sec, lang)

        # Enable toggle
        with c3:
            enabled = st.toggle("", value=bool(sec["is_enabled"]),
                                key=f"en_{sec['id']}")
            if enabled != bool(sec["is_enabled"]):
                sb.table("lecture_sections")\
                  .update({"is_enabled": enabled})\
                  .eq("id", sec["id"]).execute()
                st.rerun()

        # Delete
        with c5:
            if st.button("🗑️", key=f"del_{sec['id']}"):
                sb.table("lecture_sections").delete().eq("id", sec["id"]).execute()
                st.rerun()


def _section_config_form(sb, sec, lang):
    """Per-section-type config form."""
    import json
    from app.schemas.section_configs import validate_section_config

    section_type = sec["section_type"]
    try:
        config = json.loads(sec.get("config_json") or "{}")
    except Exception:
        config = {}

    new_config = {}

    if section_type in ("video", "hw_review_video"):
        yt  = st.text_input("رابط YouTube", value=config.get("youtube_url",""),
                             key=f"yt_{sec['id']}")
        new_config = {"youtube_url": yt or None}

    elif section_type == "quiz":
        # List exams for this lecture's subject
        try:
            lec_res  = sb.table("lectures").select("subject_id").eq("id", sec["lecture_id"]).single().execute()
            subj_id  = lec_res.data["subject_id"] if lec_res.data else None
            exams    = sb.table("exams").select("id, title").eq("subject_id", subj_id).execute().data or []
            e_opts   = {e["title"]: e["id"] for e in exams}
            if e_opts:
                cur_exam = config.get("exam_id","")
                cur_label = next((k for k,v in e_opts.items() if v==cur_exam), list(e_opts.keys())[0])
                chosen_e = st.selectbox("اختر الامتحان", list(e_opts.keys()),
                                        index=list(e_opts.keys()).index(cur_label),
                                        key=f"exam_{sec['id']}")
                dur = st.number_input("المدة (دقيقة)", 1, 240,
                                      value=config.get("duration_minutes",30),
                                      key=f"dur_{sec['id']}")
                new_config = {"exam_id": e_opts[chosen_e], "duration_minutes": int(dur)}
            else:
                st.info("لا توجد امتحانات. أنشئ امتحاناً أولاً.")
                return
        except Exception as e:
            st.error(f"خطأ: {e}")
            return

    elif section_type == "homework":
        try:
            lec_res = sb.table("lectures").select("subject_id").eq("id", sec["lecture_id"]).single().execute()
            subj_id = lec_res.data["subject_id"] if lec_res.data else None
            hws     = sb.table("homework").select("id, title").eq("subject_id", subj_id).execute().data or []
            h_opts  = {h["title"]: h["id"] for h in hws}
            if h_opts:
                cur_hw = config.get("hw_id","")
                cur_label = next((k for k,v in h_opts.items() if v==cur_hw), list(h_opts.keys())[0])
                chosen_h = st.selectbox("اختر الواجب", list(h_opts.keys()),
                                        index=list(h_opts.keys()).index(cur_label),
                                        key=f"hw_{sec['id']}")
                new_config = {"hw_id": h_opts[chosen_h]}
            else:
                st.info("لا توجد واجبات.")
                return
        except Exception as e:
            st.error(f"خطأ: {e}")
            return

    elif section_type == "pdf_notes":
        title = st.text_input("عنوان الـ PDF", value=config.get("title",""),
                              key=f"pdft_{sec['id']}")
        allow = st.checkbox("السماح بالتنزيل",
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

    # Save button
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
        # Get teacher's subjects
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
