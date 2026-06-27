from __future__ import annotations
import re
import hashlib
import streamlit as st
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.security import get_supabase, get_supabase_admin, clear_session
from app.core.exceptions import AuthError

_COMMON_PASSWORDS = {
    "12345678", "password", "admin123", "admin1234", "admin12345",
    "123456789", "qwerty123", "iloveyou", "password1", "welcome1",
}


class AuthService:

    # ─────────────────────────────────────────────────────────
    # VALIDATION HELPERS
    # ─────────────────────────────────────────────────────────
    def _validate_password(self, password: str) -> None:
        if len(password) < 8:
            raise AuthError("كلمة المرور أقل من 8 أحرف")
        if not re.search(r"[A-Za-z]", password):
            raise AuthError("كلمة المرور تحتاج حرف واحد على الأقل")
        if not re.search(r"\d", password):
            raise AuthError("كلمة المرور تحتاج رقم واحد على الأقل")
        if password.lower() in _COMMON_PASSWORDS:
            raise AuthError("كلمة المرور شائعة جداً، اختر كلمة أصعب")

    def _check_rate_limit(self, email: str) -> None:
        """Block login after 5 failed attempts in 15 minutes."""
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
            sb = get_supabase_admin()
            result = sb.table("login_history") \
                       .select("id", count="exact") \
                       .eq("email", email.strip().lower()) \
                       .eq("success", False) \
                       .gte("created_at", cutoff) \
                       .execute()
            if (result.count or 0) >= 5:
                raise AuthError("محاولات تسجيل دخول كثيرة — انتظر 15 دقيقة ثم حاول مجدداً")
        except AuthError:
            raise
        except Exception:
            pass  # Never block login if history table missing

    def _log_login(self, email: str, success: bool) -> None:
        try:
            get_supabase_admin().table("login_history").insert({
                "email":      email.strip().lower(),
                "success":    success,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────
    # LOGIN
    # ─────────────────────────────────────────────────────────
    def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()

        # Rate limit check
        self._check_rate_limit(email)

        try:
            sb = get_supabase()
            res = sb.auth.sign_in_with_password({
                "email":    email,
                "password": password,
            })
            user    = res.user
            session = res.session

            # Fetch profile
            profile = sb.table("profiles") \
                        .select("*") \
                        .eq("id", user.id) \
                        .single().execute()
            profile_data = profile.data or {}

            # ── FIX-03: Block frozen / banned / deleted accounts ──
            status = profile_data.get("account_status", "active")
            if status != "active":
                sb.auth.sign_out()
                self._log_login(email, success=False)
                messages = {
                    "frozen":    "الحساب مجمّد — تواصل مع المشرف",
                    "suspended": "الحساب موقوف مؤقتاً — تواصل مع المشرف",
                    "banned":    "تم حظر هذا الحساب",
                    "deleted":   "هذا الحساب محذوف",
                }
                raise AuthError(messages.get(status, "الحساب غير نشط"))

            user_data = {
                "id":         user.id,
                "email":      user.email,
                "full_name":  profile_data.get("full_name", user.email),
                "avatar_url": profile_data.get("avatar_url"),
                "bio":        profile_data.get("bio"),
                "language":   profile_data.get("language", "ar"),
            }

            st.session_state.user          = user_data
            st.session_state.access_token  = session.access_token
            st.session_state.refresh_token = session.refresh_token

            self._load_role_permissions(sb)
            self._log_login(email, success=True)

            return user_data

        except AuthError:
            self._log_login(email, success=False)
            raise
        except Exception as e:
            self._log_login(email, success=False)
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
        # Password strength validation
        self._validate_password(password)

        try:
            sb = get_supabase()
            res = sb.auth.sign_up({
                "email":   email.strip().lower(),
                "password": password,
                "options": {"data": {"full_name": full_name}},
            })
            if not res.user:
                raise AuthError("فشل إنشاء الحساب")

            user_id = res.user.id

            sb.table("profiles").update({
                "full_name": full_name.strip(),
                "language":  language,
            }).eq("id", user_id).execute()

            admin_sb = get_supabase_admin()
            student_role = admin_sb.table("roles") \
                                   .select("id") \
                                   .eq("name", "student") \
                                   .single().execute()
            if student_role.data:
                admin_sb.table("user_roles").insert({
                    "user_id": user_id,
                    "role_id": student_role.data["id"],
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
                          created_by: str,
                          extra: Optional[dict] = None) -> dict:
        try:
            admin_sb = get_supabase_admin()

            res = admin_sb.auth.admin.create_user({
                "email":          email.strip().lower(),
                "password":       password,
                "email_confirm":  True,
                "user_metadata":  {"full_name": full_name},
            })
            user_id = res.user.id

            profile_update = {"full_name": full_name.strip()}
            if extra:
                for field in ("phone", "grade_id", "language"):
                    if extra.get(field):
                        profile_update[field] = extra[field]

            admin_sb.table("profiles").update(profile_update).eq("id", user_id).execute()

            role = admin_sb.table("roles") \
                           .select("id") \
                           .eq("name", role_name) \
                           .single().execute()
            if role.data:
                admin_sb.table("user_roles").insert({
                    "user_id":    user_id,
                    "role_id":    role.data["id"],
                    "granted_by": created_by,
                }).execute()

            admin_sb.table("audit_logs").insert({
                "user_id":   created_by,
                "action":    "admin_create_user",
                "entity":    "profile",
                "entity_id": user_id,
                "metadata":  {"email": email, "role": role_name},
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
