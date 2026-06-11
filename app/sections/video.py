import streamlit as st
from app.services.progress_service import ProgressService


def render_video(config: dict, student_id: str, lang: str, section_id: str) -> None:
    """
    Renders a video section.
    Supports: YouTube embed or Supabase Storage video.
    Marks section complete on open (PDF-style) since we can't track JS events easily.
    """
    youtube_url = config.get("youtube_url")
    video_path  = config.get("video_path")
    autoplay    = config.get("autoplay", False)

    if youtube_url:
        # Convert to embed URL
        video_id = _extract_youtube_id(str(youtube_url))
        if video_id:
            autoplay_param = "?autoplay=1" if autoplay else ""
            embed_url = f"https://www.youtube.com/embed/{video_id}{autoplay_param}"
            st.markdown(f"""
            <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;
                        border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.12)">
                <iframe src="{embed_url}"
                    style="position:absolute;top:0;left:0;width:100%;height:100%"
                    frameborder="0" allowfullscreen
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope">
                </iframe>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("رابط YouTube غير صحيح")
            return

    elif video_path:
        # Supabase Storage video
        try:
            from app.core.security import get_supabase
            sb = get_supabase()
            signed_url = sb.storage.from_("videos").create_signed_url(video_path, 3600)
            st.video(signed_url["signedURL"])
        except Exception as e:
            st.error(f"خطأ في تحميل الفيديو: {e}")
            return
    else:
        st.info("لم يتم إضافة فيديو بعد")
        return

    # Mark section complete on view
    ProgressService().mark_section_complete(student_id, section_id)


def _extract_youtube_id(url: str) -> str | None:
    """Extract video ID from various YouTube URL formats."""
    import re
    patterns = [
        r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
