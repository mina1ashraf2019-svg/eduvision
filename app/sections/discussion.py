import streamlit as st
from datetime import datetime
from app.core.security import get_supabase


def render_discussion(config: dict, student_id: str, lang: str, section_id: str):
    sb      = get_supabase()
    prompt  = config.get("prompt","")
    anon    = config.get("allow_anonymous", False)

    if prompt:
        st.info(f"💬 {prompt}")

    # Load top-level comments
    try:
        res = sb.table("discussions")\
                .select("*, profiles(full_name)")\
                .eq("section_id", section_id)\
                .is_("parent_id", "null")\
                .order("created_at", desc=True)\
                .limit(50).execute()
        comments = res.data or []
    except Exception as e:
        st.error(f"خطأ في تحميل التعليقات: {e}")
        return

    # Post new comment
    with st.form(f"disc_form_{section_id}"):
        content = st.text_area("💬 " + ("اكتب تعليقك" if lang=="ar" else "Write a comment"),
                               height=80)
        is_anon = st.checkbox("نشر كمجهول" if lang=="ar" else "Post anonymously") if anon else False
        if st.form_submit_button("📤 " + ("نشر" if lang=="ar" else "Post"),
                                 use_container_width=True):
            if content.strip():
                try:
                    sb.table("discussions").insert({
                        "section_id":   section_id,
                        "user_id":      student_id,
                        "content":      content.strip(),
                        "is_anonymous": is_anon,
                    }).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"خطأ: {e}")

    st.divider()

    # Display comments
    for c in comments:
        name = ("مجهول" if lang=="ar" else "Anonymous") if c.get("is_anonymous") \
               else (c.get("profiles") or {}).get("full_name","—")
        date = str(c.get("created_at",""))[:16]
        st.markdown(f"""
        <div style="background:#F8FAFC;border-radius:8px;padding:12px 16px;
                    border-left:3px solid #3B82F6;margin-bottom:8px">
            <div style="font-weight:700;color:#0F2D6B;font-size:0.9rem">{name}</div>
            <div style="color:#374151;margin:6px 0">{c['content']}</div>
            <div style="color:#9CA3AF;font-size:0.78rem">{date}</div>
        </div>
        """, unsafe_allow_html=True)
