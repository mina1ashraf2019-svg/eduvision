from __future__ import annotations
import streamlit as st
from typing import Optional
from app.core.security import get_supabase, get_supabase_admin, clear_session
from app.core.exceptions import AuthError


class AuthService:

    # ─────────────────────────────────────────────────────────
    # LOGIN
    # ─────────────────────────────────────────────────────────
    def login(self, email: str, password: str) -> dict:
        """
        Sign in with email/password.
        Returns user dict and stores in session.
        """
        try:
            sb = get_supabase()
            res = sb.auth.sign_in_with_password({
                "email": email.strip().lower(),
                "password": password
            })
            user = res.user
            session = res.session

            # Load profile
            profile = sb.table("profiles").select("*").eq("id", user.id).single().execute()

            user_data = {
                "id":         user.id,
                "email":      user.email,
                "full_name":  profile.data.get("full_name", user.email),
                "avatar_url": profile.data.get("avatar_url"),
                "bio":        profile.data.get("bio"),
                "language":   profile.data.get("language", "ar"),
            }

            # Store in session
            st.session_state.user          = user_data
            st.session_state.access_token  = session.access_token
            st.session_state.refresh_token = session.refresh_token

            # Load role & permissions (warm cache)
            self._load_role_permissions(sb)

            return user_data

        except AuthError:
            raise
        except Exception as e:
            err = str(e)
            if "Invalid login" in err or "invalid_credentials" in err:
                raise AuthError("البريد الإلكتروني أو كلمة المرور غير صحيحة")
            if "Email not confirmed" in err:
                raise AuthError("يرجى تأكيد بريدك الإلكتروني أولاً")
            raise AuthError(f"خطأ في تسجيل الدخول: {err}")

    # ─────────────────────────────────────────────────────────
    # REGISTER
    # ─────────────────────────────────────────────────────────
    def register(self, email: str, password: str, full_name: str,
                 language: str = "ar") -> dict:
        """
        Register new student account.
        Admin/teacher accounts are created by admin only.
        """
        try:
            sb = get_supabase()
            res = sb.auth.sign_up({
                "email": email.strip().lower(),
                "password": password,
                "options": {
                    "data": {"full_name": full_name}
                }
            })
            if not res.user:
                raise AuthError("فشل إنشاء الحساب")

            user_id = res.user.id

            # Update profile with full_name & language
            sb.table("profiles").update({
                "full_name": full_name,
                "language":  language
            }).eq("id", user_id).execute()

            # Assign student role
            admin_sb = get_supabase_admin()
            student_role = admin_sb.table("roles").select("id").eq("name", "student").single().execute()
            if student_role.data:
                admin_sb.table("user_roles").insert({
                    "user_id": user_id,
                    "role_id": student_role.data["id"]
                }).execute()

            return {"user_id": user_id, "email": email}

        except AuthError:
            raise
        except Exception as e:
            err = str(e)
            if "already registered" in err or "already been registered" in err:
                raise AuthError("هذا البريد الإلكتروني مسجل مسبقاً")
            raise AuthError(f"خطأ في إنشاء الحساب: {err}")

    # ─────────────────────────────────────────────────────────
    # LOGOUT
    # ─────────────────────────────────────────────────────────
    def logout(self):
        try:
            sb = get_supabase()
            sb.auth.sign_out()
        except Exception:
            pass
        finally:
            clear_session()

    # ─────────────────────────────────────────────────────────
    # PASSWORD RESET
    # ─────────────────────────────────────────────────────────
    def request_password_reset(self, email: str):
        try:
            sb = get_supabase()
            sb.auth.reset_password_email(email.strip().lower())
        except Exception as e:
            raise AuthError(f"خطأ في إرسال رابط الاسترداد: {e}")

    # ─────────────────────────────────────────────────────────
    # CREATE USER (admin only)
    # ─────────────────────────────────────────────────────────
    def admin_create_user(self, email: str, password: str,
                          full_name: str, role_name: str,
                          created_by: str) -> dict:
        """Create teacher/admin accounts — requires service role."""
        try:
            admin_sb = get_supabase_admin()

            # Create auth user
            res = admin_sb.auth.admin.create_user({
                "email": email.strip().lower(),
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name}
            })
            user_id = res.user.id

            # Update profile
            admin_sb.table("profiles").update({
                "full_name": full_name
            }).eq("id", user_id).execute()

            # Assign role
            role = admin_sb.table("roles").select("id").eq("name", role_name).single().execute()
            if role.data:
                admin_sb.table("user_roles").insert({
                    "user_id":    user_id,
                    "role_id":    role.data["id"],
                    "granted_by": created_by
                }).execute()

            # Audit log
            admin_sb.table("audit_logs").insert({
                "user_id":   created_by,
                "action":    "admin_create_user",
                "entity":    "profile",
                "entity_id": user_id,
                "metadata":  {"email": email, "role": role_name}
            }).execute()

            return {"user_id": user_id}

        except Exception as e:
            raise AuthError(f"خطأ في إنشاء المستخدم: {e}")

    # ─────────────────────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────────────────────
    def _load_role_permissions(self, sb):
        try:
            role_res  = sb.rpc("get_my_role").execute()
            perms_res = sb.rpc("get_my_permissions").execute()
            st.session_state.role        = role_res.data or "student"
            st.session_state.permissions = perms_res.data or []
        except Exception:
            st.session_state.role        = "student"
            st.session_state.permissions = []
