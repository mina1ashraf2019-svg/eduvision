import streamlit as st
from app.services.progress_service import ProgressService


def render_links(config: dict, student_id: str, lang: str, section_id: str):
    """
    External links section.
    config.links = [{"label": str, "url": str, "desc": str}]
    """
    links = config.get("links", [])

    st.markdown("#### 🔗 الروابط الخارجية")

    if not links:
        st.info("لا توجد روابط في هذا القسم.")
        ProgressService().mark_section_complete(student_id, section_id)
        return

    for lnk in links:
        label = lnk.get("label", "رابط")
        url   = lnk.get("url", "")
        desc  = lnk.get("desc", "")

        if not url:
            continue

        # Detect link type for icon
        icon = "🔗"
        if "youtube.com" in url or "youtu.be" in url:
            icon = "▶️"
        elif "drive.google.com" in url:
            icon = "📁"
        elif "docs.google.com" in url:
            icon = "📝"
        elif url.endswith(".pdf"):
            icon = "📄"

        st.markdown(f"""
        <div style="border:1px solid #E5E7EB;border-radius:10px;
                    padding:14px 18px;margin-bottom:10px;
                    background:#F9FAFB">
            <div style="display:flex;align-items:center;gap:10px">
                <span style="font-size:1.4rem">{icon}</span>
                <div>
                    <a href="{url}" target="_blank"
                       style="font-weight:700;font-size:1rem;
                              color:#2563EB;text-decoration:none">
                        {label}
                    </a>
                    {'<div style="color:#6B7280;font-size:0.85rem;margin-top:2px">' + desc + '</div>' if desc else ''}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Auto-complete
    ProgressService().mark_section_complete(student_id, section_id)
