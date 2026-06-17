import streamlit as st
from app.services.progress_service import ProgressService


def render_hw_upload(config: dict, student_id: str, lang: str, section_id: str):
    """
    Homework file upload section.
    - Student uploads a file → saved to Supabase Storage hw_uploads bucket
    - Path stored in hw_uploads table
    - Marks section complete after successful upload
    """
    title         = config.get("title", "رفع الواجب")
    allowed_types = config.get("allowed_types", ["pdf", "doc", "docx", "jpg", "png"])
    max_mb        = config.get("max_mb", 10)

    st.markdown(f"#### 📤 {title}")

    # Check if already submitted
    try:
        from app.core.security import get_supabase
        sb = get_supabase()

        existing = sb.table("hw_uploads")\
                     .select("id, file_name, uploaded_at, grade, feedback")\
                     .eq("student_id", student_id)\
                     .eq("section_id", section_id)\
                     .order("uploaded_at", desc=True)\
                     .limit(1).execute().data or []

        if existing:
            sub = existing[0]
            st.success(f"✅ تم رفع الواجب: **{sub['file_name']}**")
            st.caption(f"وقت الرفع: {str(sub['uploaded_at'])[:19]}")

            if sub.get("grade") is not None:
                st.info(f"📊 الدرجة: **{sub['grade']}** | 💬 {sub.get('feedback','—')}")
            else:
                st.caption("⏳ في انتظار التصحيح من المعلم")

            if st.button("🔄 رفع ملف جديد (استبدال)", key=f"reupload_{section_id}"):
                st.session_state[f"show_upload_{section_id}"] = True
                st.rerun()

            if not st.session_state.get(f"show_upload_{section_id}"):
                return

    except Exception as e:
        st.warning(f"تعذّر التحقق من الواجبات السابقة: {e}")

    # Upload widget
    st.caption(f"الأنواع المسموحة: {', '.join(allowed_types)} | الحجم الأقصى: {max_mb} MB")

    uploaded_file = st.file_uploader(
        "اختر الملف",
        type=allowed_types,
        key=f"hw_file_{section_id}",
    )

    if uploaded_file:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        if file_size_mb > max_mb:
            st.error(f"❌ حجم الملف ({file_size_mb:.1f} MB) يتجاوز الحد المسموح ({max_mb} MB)")
            return

        st.info(f"📎 {uploaded_file.name} ({file_size_mb:.2f} MB)")

        if st.button("📤 رفع الملف", key=f"submit_hw_{section_id}", type="primary"):
            with st.spinner("جاري الرفع..."):
                try:
                    from app.core.security import get_supabase
                    sb = get_supabase()

                    # Upload to Supabase Storage
                    file_bytes = uploaded_file.read()
                    storage_path = f"{student_id}/{section_id}/{uploaded_file.name}"

                    sb.storage.from_("hw_uploads").upload(
                        path=storage_path,
                        file=file_bytes,
                        file_options={"content-type": uploaded_file.type or "application/octet-stream",
                                      "upsert": "true"},
                    )

                    # Save record in DB
                    sb.table("hw_uploads").upsert({
                        "student_id":  student_id,
                        "section_id":  section_id,
                        "file_name":   uploaded_file.name,
                        "file_path":   storage_path,
                        "file_size":   uploaded_file.size,
                    }, on_conflict="student_id,section_id").execute()

                    # Clear re-upload flag
                    st.session_state.pop(f"show_upload_{section_id}", None)

                    st.success("✅ تم رفع الملف بنجاح!")
                    ProgressService().mark_section_complete(student_id, section_id)
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ خطأ في الرفع: {e}")
