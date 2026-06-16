import streamlit as st
from datetime import date
from app.core.security import get_supabase_admin, get_current_user_id
from app.services.attendance_service import AttendanceService
from translations import get_lang


def show_attendance():
    lang = get_lang()
    uid  = get_current_user_id()
    sb   = get_supabase_admin()
    svc  = AttendanceService()

    st.title("📋 " + ("الحضور والغياب" if lang=="ar" else "Attendance"))

    # Subject selector
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

    # Today's stats
    stats = svc.get_today_stats(sid)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ حاضر اليوم",   stats["present"])
    c2.metric("❌ غائب اليوم",   stats["absent"])
    c3.metric("🕐 متأخر اليوم",  stats["late"])
    c4.metric("📊 الإجمالي",     stats["total"])

    st.divider()
    tab1, tab2 = st.tabs(["📝 تسجيل حضور", "📊 سجل الحضور"])

    # ── MANUAL CHECK-IN ───────────────────────────────────────
    with tab1:
        st.subheader("📝 تسجيل حضور يدوي")
        try:
            enrolled = sb.table("enrollments")\
                         .select("student_id, profiles(id, full_name)")\
                         .eq("subject_id", sid).execute().data or []
            students = [r["profiles"] for r in enrolled if r.get("profiles")]
        except Exception:
            students = []

        if not students:
            st.info("لا يوجد طلاب مسجلون في هذه المادة.")
        else:
            today = date.today().isoformat()
            # Get today's records
            try:
                today_records = sb.table("attendance_records").select("student_id, status")\
                                  .eq("subject_id", sid).eq("date", today).execute().data or []
                attended = {r["student_id"]: r["status"] for r in today_records}
            except Exception:
                attended = {}

            for stu in students:
                current = attended.get(stu["id"], "absent")
                icon    = "✅" if current=="present" else "🕐" if current=="late" else "❌"
                c1, c2, c3 = st.columns([4, 2, 2])
                c1.markdown(f"{icon} **{stu['full_name']}**")
                with c2:
                    status = st.selectbox("", ["present","late","absent","excused"],
                                          index=["present","late","absent","excused"].index(current),
                                          key=f"att_{stu['id']}",
                                          label_visibility="collapsed")
                with c3:
                    if st.button("💾", key=f"save_att_{stu['id']}"):
                        svc.check_in(stu["id"], sid, method="manual", recorded_by=uid)
                        if status != "present":
                            svc.update_status(stu["id"], sid, today, status, uid)
                        st.rerun()
                st.divider()

    # ── ATTENDANCE HISTORY ────────────────────────────────────
    with tab2:
        st.subheader("📊 سجل الحضور")
        c1, c2 = st.columns(2)
        with c1:
            from_d = st.date_input("من", value=date.today().replace(day=1))
        with c2:
            to_d   = st.date_input("إلى", value=date.today())

        records = svc.get_subject_attendance(sid, str(from_d), str(to_d))
        if records:
            import pandas as pd
            df = pd.DataFrame([{
                "الطالب": (r.get("profiles") or {}).get("full_name","—"),
                "التاريخ": str(r["date"]),
                "الحالة":  {"present":"✅ حاضر","absent":"❌ غائب",
                            "late":"🕐 متأخر","excused":"📋 بعذر"}.get(r["status"],r["status"]),
                "الطريقة": r.get("method","manual"),
            } for r in records])
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Export
            buf = __import__("io").BytesIO()
            df.to_excel(buf, index=False)
            buf.seek(0)
            st.download_button("📥 تحميل Excel", buf,
                               file_name=f"attendance_{chosen}_{from_d}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("لا توجد سجلات في هذه الفترة.")
