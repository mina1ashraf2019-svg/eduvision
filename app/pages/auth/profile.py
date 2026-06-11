import streamlit as st
from app.core.security import get_supabase, get_current_user_id
from translations import get_lang


def show_profile():
    lang = get_lang()
    sb   = get_supabase()
    uid  = get_current_user_id()
    user = st.session_state.user

    st.title("👤 " + ("ملفي الشخصي" if lang=="ar" else "My Profile"))

    # Header
    c1, c2 = st.columns([1, 3])
    with c1:
        initials = user["full_name"][0].upper() if user.get("full_name") else "?"
        st.markdown(f"""
        <div style="width:90px;height:90px;border-radius:50%;background:#3B82F6;
                    display:flex;align-items:center;justify-content:center;
                    font-size:2.5rem;font-weight:900;color:white">
            {initials}
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"## {user['full_name']}")
        st.caption(f"📧 {user.get('email','—')}")

    st.divider()

    tab1, tab2 = st.tabs([
        "🔒 " + ("تغيير كلمة المرور" if lang=="ar" else "Change Password"),
        "🌐 " + ("اللغة" if lang=="ar" else "Language"),
    ])

    with tab1:
        with st.form("change_pass"):
            old_p  = st.text_input("كلمة المرور الحالية" if lang=="ar" else "Current Password",
                                   type="password")
            new_p  = st.text_input("كلمة المرور الجديدة" if lang=="ar" else "New Password",
                                   type="password")
            new_p2 = st.text_input("تأكيد كلمة المرور" if lang=="ar" else "Confirm Password",
                                   type="password")
            if st.form_submit_button("💾 " + ("حفظ" if lang=="ar" else "Save"),
                                     use_container_width=True):
                if not all([old_p, new_p, new_p2]):
                    st.error("أدخل جميع البيانات")
                elif new_p != new_p2:
                    st.error("كلمتا المرور غير متطابقتين")
                elif len(new_p) < 8:
                    st.error("كلمة المرور أقل من 8 أحرف")
                else:
                    try:
                        sb.auth.update_user({"password": new_p})
                        st.success("✅ تم تغيير كلمة المرور")
                    except Exception as e:
                        st.error(f"خطأ: {e}")

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🇸🇦 العربية", use_container_width=True,
                         type="primary" if lang=="ar" else "secondary"):
                sb.table("profiles").update({"language":"ar"}).eq("id",uid).execute()
                st.session_state.user["language"] = "ar"
                st.rerun()
        with c2:
            if st.button("🇬🇧 English", use_container_width=True,
                         type="primary" if lang=="en" else "secondary"):
                sb.table("profiles").update({"language":"en"}).eq("id",uid).execute()
                st.session_state.user["language"] = "en"
                st.rerun()
