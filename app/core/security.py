from __future__ import annotations
import streamlit as st
from functools import wraps
from typing import Optional


def _get_client(use_service_role: bool = False):
    from supabase import create_client
    from app.core.config import get_settings
    cfg = get_settings()
    key = cfg["supabase_service_role_key"] if use_service_role else cfg["supabase_anon_key"]
    return create_client(cfg["supabase_url"], key)


@st.cache_resource
def get_supabase_admin():
    return _get_client(use_service_role=True)


def get_supabase():
    """
    Returns a fresh Supabase client with the current user's session injected.
    NO cache — so auth.uid() works correctly in RLS policies every call.
    """
    client = _get_client(use_service_role=False)
    access_token  = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    if access_token and refresh_token:
        try:
            client.auth.set_session(access_token, refresh_token)
        except Exception:
            pass
    return client


def get_current_user() -> Optional[dict]:
    return st.session_state.get("user")


def get_current_user_id() -> Optional[str]:
    user = get_current_user()
    return user["id"] if user else None


def is_authenticated() -> bool:
    return get_current_user() is not None


def get_my_permissions() -> list[str]:
    if "permissions" in st.session_state:
        return st.session_state.permissions
    try:
        res = get_supabase().rpc("get_my_permissions").execute()
        perms = res.data or []
        st.session_state.permissions = perms
        return perms
    except Exception:
        return []


def has_permission(perm: str) -> bool:
    return perm in get_my_permissions()


def get_my_role() -> str:
    if "role" in st.session_state:
        return st.session_state.role
    try:
        res = get_supabase().rpc("get_my_role").execute()
        role = res.data or "student"
        st.session_state.role = role
        return role
    except Exception:
        return "student"


def require_permission(perm: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_authenticated():
                st.error("🔒 يرجى تسجيل الدخول أولاً")
                st.stop()
            if not has_permission(perm):
                st.error(f"🚫 ليس لديك صلاحية: {perm}")
                st.stop()
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            st.error("🔒 يرجى تسجيل الدخول أولاً")
            st.stop()
        return fn(*args, **kwargs)
    return wrapper


def clear_session():
    for key in ["user","permissions","role","access_token","refresh_token",
                "active_subject","active_lecture","active_teacher","show_profile",
                "admin_page","teacher_page","student_page","view_lecture_list"]:
        st.session_state.pop(key, None)
