import streamlit as st
from app.services.auth_service import AuthService
from app.core.exceptions import AuthError
from translations import t


def show_auth():
    auth = AuthService()
    lang = st.session_state.get("lang", "ar")

    # ── Language switcher ──────────────────────────────────────
    col_spacer, col_ar, col_en = st.columns([5, 1, 1])
    with col_ar:
        if st.button("العربية", use_container_width=True,
                     type="primary" if lang == "ar" else "secondary"):
            st.session_state.lang = "ar"
            st.rerun()
    with col_en:
        if st.button("English", use_container_width=True,
                     type="primary" if lang == "en" else "secondary"):
            st.session_state.lang = "en"
            st.rerun()

    # ── Header ─────────────────────────────────────────────────
    st.markdown(f"""
    <div style='text-align:center; padding:40px 0 24px'>
        <div style='font-size:3.5rem'>🎓</div>
        <div style='font-size:2.2rem; font-weight:900; color:#0F2D6B'>EduVision</div>
        <div style='color:#6B7280; font-size:0.95rem'>
            {'منصة التعليم الذكي' if lang == 'ar' else 'Smart Learning Platform'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs([
        f"🔑 {t('login', lang)}",
        f"📝 {t('register', lang)}"
    ])

    # ══════════════════════════════════════════════════════════
    # LOGIN TAB
    # ══════════════════════════════════════════════════════════
    with tab_login:
        with st.form("login_form"):
            email    = st.text_input(t("email", lang),    placeholder="example@email.com")
            password = st.text_input(t("password", lang), type="password")
            submitted = st.form_submit_button(t("login_btn", lang), use_container_width=True)

        if submitted:
            if not email or not password:
                st.error(t("fill_all_fields", lang))
            else:
                with st.spinner(t("loading", lang)):
                    try:
                        auth.login(email, password)
                        st.success(t("success", lang))
                        st.rerun()
                    except AuthError as e:
                        st.error(str(e))

        # Forgot password
        with st.expander("🔑 " + ("نسيت كلمة المرور؟" if lang == "ar" else "Forgot password?")):
            reset_email = st.text_input("Email", key="reset_email")
            if st.button("إرسال رابط الاسترداد" if lang == "ar" else "Send Reset Link"):
                if reset_email:
                    try:
                        auth.request_password_reset(reset_email)
                        st.success("✅ تم إرسال رابط الاسترداد على بريدك" if lang == "ar"
                                   else "✅ Reset link sent to your email")
                    except AuthError as e:
                        st.error(str(e))



    # ══════════════════════════════════════════════════════════
    # REGISTER TAB
    # ══════════════════════════════════════════════════════════
    with tab_register:
        st.info(f"🎓 {t('students_only', lang)} — {t('teachers_added_by_admin', lang)}")

        with st.form("register_form"):
            c1, c2 = st.columns(2)
            with c1:
                first_name = st.text_input(t("first_name", lang))
            with c2:
                last_name = st.text_input(t("last_name", lang))

            reg_email = st.text_input(t("email", lang), key="reg_email",
                                       placeholder="example@email.com")
            reg_pass  = st.text_input(t("password", lang), type="password", key="reg_pass",
                                       help="8 أحرف على الأقل" if lang == "ar" else "Min 8 characters")
            reg_pass2 = st.text_input(t("confirm_password", lang), type="password", key="reg_pass2")

            reg_submitted = st.form_submit_button(t("register_btn", lang), use_container_width=True)

        if reg_submitted:
            errors = _validate_register(first_name, last_name, reg_email, reg_pass, reg_pass2, lang)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                with st.spinner(t("loading", lang)):
                    try:
                        full_name = f"{first_name.strip()} {last_name.strip()}"
                        auth.register(reg_email, reg_pass, full_name, lang)
                        st.success(
                            "🎉 تم إنشاء حسابك! تحقق من بريدك لتأكيد الحساب." if lang == "ar"
                            else "🎉 Account created! Check your email to confirm."
                        )
                    except AuthError as e:
                        st.error(str(e))


def _validate_register(first, last, email, password, password2, lang) -> list[str]:
    errors = []
    if not all([first, last, email, password, password2]):
        errors.append(t("fill_all_fields", lang))
        return errors
    if password != password2:
        errors.append(t("passwords_not_match", lang))
    if len(password) < 8:
        errors.append(t("password_too_short", lang))
    if "@" not in email or "." not in email:
        errors.append(t("invalid_email", lang))
    return errors
