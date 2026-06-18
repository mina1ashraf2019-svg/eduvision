import re
import streamlit as st
from app.services.progress_service import ProgressService

_YT_PATTERNS = [
    r"(?:youtube\.com/watch\?.*v=)([a-zA-Z0-9_-]{11})",
    r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/v/)([a-zA-Z0-9_-]{11})",
    r"(?:youtube\.com/live/)([a-zA-Z0-9_-]{11})",
]


def validate_youtube_url(url: str) -> tuple[bool, str]:
    if not url or not url.strip():
        return False, "الرجاء إدخال رابط الفيديو"
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False, "الرابط يجب أن يبدأ بـ https://"
    yt_domains = ("youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com")
    if not any(d in url for d in yt_domains):
        return False, "الرابط يجب أن يكون من YouTube (youtube.com أو youtu.be)"
    video_id = _extract_youtube_id(url)
    if not video_id:
        return False, "تعذّر استخراج معرّف الفيديو — تأكد من صحة الرابط"
    return True, ""


def render_video(config: dict, student_id: str, lang: str, section_id: str) -> None:
    youtube_url = config.get("youtube_url")
    video_path  = config.get("video_path")
    autoplay    = config.get("autoplay", False)

    if youtube_url:
        is_valid, err_msg = validate_youtube_url(str(youtube_url))
        if not is_valid:
            st.error(f"❌ رابط YouTube غير صحيح: {err_msg}")
            return
        video_id = _extract_youtube_id(str(youtube_url))
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

    elif video_path:
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

    ProgressService().mark_section_complete(student_id, section_id)


def render_youtube_url_input(current_url: str = "", key: str = "yt_url") -> str:
    """
    Reusable validated YouTube URL input widget.
    key param ensures unique element ID when used multiple times on same page.
    """
    url = st.text_input(
        "رابط YouTube",
        value=current_url,
        placeholder="https://www.youtube.com/watch?v=... أو https://youtu.be/...",
        help="يدعم: روابط youtube.com/watch و youtu.be و youtube.com/shorts",
        key=key,
    )

    if url and url.strip():
        is_valid, err_msg = validate_youtube_url(url)
        if is_valid:
            video_id = _extract_youtube_id(url)
            st.success(f"✅ رابط صحيح — معرّف الفيديو: `{video_id}`")
        else:
            st.error(f"❌ {err_msg}")

    return url


def _extract_youtube_id(url: str) -> str | None:
    for pattern in _YT_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
