import streamlit as st
import os

st.set_page_config(
    page_title="EduVision",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def _load_css():
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

_load_css()

from app.core.security import (
    is_authenticated, get_my_role, has_permission, clear_session
)

if not is_authenticated():
    from app.pages.auth.login import show_auth
    show_auth()
    st.stop()

role = get_my_role()
user = st.session_state.user
lang = user.get("language", "ar")

with st.sidebar:
    st.markdown(f"### 👋 {user['full_name']}")
    role_labels = {
        "owner":    "👑 مالك",
        "admin":    "🛡️ أدمن",
        "co_admin": "🛡️ مساعد أدمن",
        "teacher":  "📚 معلم",
        "student":  "🎓 طالب",
        "cashier":  "💰 كاشير",
        "parent":   "👨‍👩‍👧 ولي أمر",
    }
    st.caption(role_labels.get(role, role.upper()))
    st.divider()

    if st.button("👤 " + ("ملفي الشخصي" if lang == "ar" else "My Profile"),
                 use_container_width=True):
        st.session_state.page = "profile"
        st.rerun()

    if st.button("🏠 " + ("الرئيسية" if lang == "ar" else "Home"),
                 use_container_width=True):
        for k in ("page", "active_subject", "active_lecture",
                  "owner_page", "admin_page", "teacher_page", "student_page"):
            st.session_state.pop(k, None)
        st.rerun()

    st.divider()
    if st.button("🚪 " + ("خروج" if lang == "ar" else "Logout"),
                 use_container_width=True):
        from app.services.auth_service import AuthService
        AuthService().logout()
        st.rerun()

page = st.session_state.get("page")

if page == "profile":
    from app.pages.auth.profile import show_profile
    show_profile()

elif page == "invoice":
    from app.pages.cashier.invoice import show_invoice
    show_invoice()

# ── Owner — unlimited access ──────────────────────────────
elif role == "owner":
    from app.pages.owner import show_owner
    show_owner()

# ── Admin / Co-Admin ─────────────────────────────────────
elif role in ("admin", "co_admin"):
    from app.pages.admin import show_admin
    show_admin()

# ── Teacher ───────────────────────────────────────────────
elif role == "teacher":
    from app.pages.teacher import show_teacher
    show_teacher()

# ── Student ───────────────────────────────────────────────
elif role == "student":
    from app.pages.student import show_student
    show_student()

# ── Cashier ───────────────────────────────────────────────
elif role == "cashier":
    from app.pages.cashier import show_cashier
    show_cashier()

# ── Parent ────────────────────────────────────────────────
elif role == "parent":
    st.title("👨‍👩‍👧 بوابة ولي الأمر")
    st.info("بوابة ولي الأمر قيد التطوير. ستتمكن قريباً من متابعة أداء طفلك.")

else:
    st.warning("⚠️ دور المستخدم غير معروف. تواصل مع المشرف.")
