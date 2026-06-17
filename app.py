import streamlit as st
import os

st.set_page_config(
    page_title="EduVision",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Load CSS ──────────────────────────────────────────────────
def _load_css():
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

_load_css()

# ── Route ─────────────────────────────────────────────────────
from app.core.security import is_authenticated, get_my_role, has_permission, clear_session

if not is_authenticated():
    from app.pages.auth.login import show_auth
    show_auth()
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────
role = get_my_role()
user = st.session_state.user
lang = user.get("language", "ar")

with st.sidebar:
    st.markdown(f"### 👋 {user['full_name']}")
    st.caption(role.upper())
    st.divider()

    if st.button("👤 " + ("ملفي الشخصي" if lang == "ar" else "My Profile"),
                 use_container_width=True):
        st.session_state.page = "profile"
        st.rerun()

    if st.button("🏠 " + ("الرئيسية" if lang == "ar" else "Home"),
                 use_container_width=True):
        st.session_state.pop("page", None)
        st.session_state.pop("active_subject", None)
        st.session_state.pop("active_lecture", None)
        st.rerun()

    st.divider()
    if st.button("🚪 " + ("خروج" if lang == "ar" else "Logout"),
                 use_container_width=True):
        from app.services.auth_service import AuthService
        AuthService().logout()
        st.rerun()

# ── Page routing ──────────────────────────────────────────────
page = st.session_state.get("page")

if page == "profile":
    from app.pages.auth.profile import show_profile
    show_profile()

elif page == "invoice":
    from app.pages.cashier.invoice import show_invoice
    show_invoice()

elif role in ("admin", "co_admin"):
    from app.pages.admin import show_admin
    show_admin()

elif role == "teacher":
    from app.pages.teacher import show_teacher
    show_teacher()

elif role == "student":
    from app.pages.student import show_student
    show_student()

elif role == "cashier":
    from app.pages.cashier import show_cashier
    show_cashier()

else:
    st.warning("⚠️ دور المستخدم غير معروف. تواصل مع المشرف.")
