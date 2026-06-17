import streamlit as st
from app.services.progress_service import ProgressService


def render_pdf_notes(config: dict, student_id: str, lang: str, section_id: str):
    """
    Renders a PDF notes section.
    - If file_path exists in Supabase Storage → show inline viewer + download button
    - Marks section complete on open
    """
    file_path     = config.get("file_path", "")
    title         = config.get("title", "ملاحظات PDF")
    allow_download = config.get("allow_download", True)
    bucket        = config.get("bucket", "notes")

    st.markdown(f"#### 📄 {title}")

    if not file_path:
        st.info("لم يتم رفع ملف PDF بعد.")
        return

    try:
        from app.core.security import get_supabase
        sb = get_supabase()

        # Generate signed URL (5 hours)
        signed = sb.storage.from_(bucket).create_signed_url(file_path, 18000)
        pdf_url = signed.get("signedURL") or signed.get("signed_url", "")

        if not pdf_url:
            st.error("تعذّر تحميل الملف. تحقق من الإعدادات.")
            return

        # Inline PDF viewer via iframe
        st.markdown(f"""
        <div style="border-radius:12px;overflow:hidden;
                    box-shadow:0 4px 20px rgba(0,0,0,0.10);margin-bottom:12px">
            <iframe src="{pdf_url}"
                width="100%" height="700px"
                style="border:none;display:block">
            </iframe>
        </div>
        """, unsafe_allow_html=True)

        # Download button
        if allow_download:
            st.markdown(f"""
            <a href="{pdf_url}" target="_blank" download
               style="display:inline-block;padding:8px 20px;background:#3B82F6;
                      color:white;border-radius:8px;text-decoration:none;
                      font-weight:600;margin-top:4px">
                ⬇️ تحميل الملف
            </a>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"خطأ في تحميل الـ PDF: {e}")
        return

    # Mark complete on view
    ProgressService().mark_section_complete(student_id, section_id)
