import streamlit as st
from app.services.progress_service import ProgressService


def render_attachments(config: dict, student_id: str, lang: str, section_id: str):
    """
    Attachments section — list of downloadable files from Supabase Storage.
    config.files = [{"name": str, "path": str, "bucket": str, "description": str}]
    """
    files = config.get("files", [])

    st.markdown("#### 📎 المرفقات")

    if not files:
        st.info("لا توجد مرفقات في هذا القسم.")
        ProgressService().mark_section_complete(student_id, section_id)
        return

    try:
        from app.core.security import get_supabase
        sb = get_supabase()

        for i, f in enumerate(files):
            name        = f.get("name", f"ملف {i+1}")
            path        = f.get("path", "")
            bucket      = f.get("bucket", "attachments")
            description = f.get("description", "")

            if not path:
                continue

            try:
                signed  = sb.storage.from_(bucket).create_signed_url(path, 3600)
                dl_url  = signed.get("signedURL") or signed.get("signed_url", "")
            except Exception:
                dl_url = ""

            # File icon by extension
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            icon = {
                "pdf": "📄", "doc": "📝", "docx": "📝",
                "xls": "📊", "xlsx": "📊", "ppt": "📊", "pptx": "📊",
                "jpg": "🖼️", "jpeg": "🖼️", "png": "🖼️",
                "zip": "🗜️", "rar": "🗜️",
            }.get(ext, "📁")

            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"{icon} **{name}**")
                if description:
                    st.caption(description)
            with col2:
                if dl_url:
                    st.markdown(f"""
                    <a href="{dl_url}" target="_blank"
                       style="display:inline-block;padding:6px 14px;
                              background:#3B82F6;color:white;border-radius:6px;
                              text-decoration:none;font-size:0.85rem;font-weight:600">
                        ⬇️ تحميل
                    </a>
                    """, unsafe_allow_html=True)
                else:
                    st.caption("غير متاح")

            st.divider()

    except Exception as e:
        st.error(f"خطأ في تحميل المرفقات: {e}")
        return

    # Auto-complete
    ProgressService().mark_section_complete(student_id, section_id)
