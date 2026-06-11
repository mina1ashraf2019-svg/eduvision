from __future__ import annotations
import secrets, string
from datetime import datetime
from app.core.security import get_supabase, get_supabase_admin
from app.core.exceptions import AccessCodeError, EnrollmentError


class AccessCodeService:

    def _generate_code(self, length: int = 8) -> str:
        chars = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(chars) for _ in range(length))

    def _code_exists(self, code: str) -> bool:
        try:
            sb = get_supabase_admin()
            res = sb.table("access_codes").select("id").eq("code", code).execute()
            return bool(res.data)
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────
    # CREATE BATCH
    # ─────────────────────────────────────────────────────────
    def create_batch(self, subject_id: str, batch_name: str, description: str,
                     quantity: int, max_uses: int, expires_at,
                     created_by: str) -> dict:
        try:
            sb = get_supabase_admin()

            # Create batch record
            batch_res = sb.table("code_batches").insert({
                "subject_id":  subject_id,
                "batch_name":  batch_name,
                "description": description,
                "total_codes": quantity,
                "max_uses":    max_uses,
                "expires_at":  str(expires_at) if expires_at else None,
                "created_by":  created_by,
            }).execute()
            batch = batch_res.data[0]

            # Generate codes
            codes_to_insert = []
            for _ in range(quantity):
                code = self._generate_code()
                while self._code_exists(code):
                    code = self._generate_code()
                codes_to_insert.append({
                    "batch_id":   batch["id"],
                    "subject_id": subject_id,
                    "code":       code,
                    "max_uses":   max_uses,
                    "expires_at": str(expires_at) if expires_at else None,
                })

            codes_res = sb.table("access_codes").insert(codes_to_insert).execute()

            # Audit log
            sb.table("audit_logs").insert({
                "user_id":   created_by,
                "action":    "create_batch",
                "entity":    "code_batch",
                "entity_id": batch["id"],
                "metadata":  {"quantity": quantity, "subject_id": subject_id, "batch_name": batch_name}
            }).execute()

            return {"batch": batch, "codes": codes_res.data}

        except Exception as e:
            raise AccessCodeError(f"خطأ في إنشاء الباتش: {e}")

    # ─────────────────────────────────────────────────────────
    # ACTIVATE CODE
    # ─────────────────────────────────────────────────────────
    def activate_code(self, student_id: str, code: str) -> tuple[bool, str]:
        try:
            sb = get_supabase_admin()

            # Fetch code
            res = sb.table("access_codes")\
                    .select("*")\
                    .eq("code", code.strip().upper())\
                    .single().execute()

            if not res.data:
                return False, "الكود غير موجود"

            record = res.data

            if not record["is_active"]:
                return False, "الكود غير نشط"

            if record["max_uses"] > 0 and record["uses_count"] >= record["max_uses"]:
                return False, "الكود استُخدم بالفعل"

            if record["expires_at"]:
                expires = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
                if expires < datetime.utcnow().replace(tzinfo=expires.tzinfo):
                    return False, "الكود منتهي الصلاحية"

            # Check not already enrolled
            enrolled = sb.table("enrollments")\
                         .select("id")\
                         .eq("student_id", student_id)\
                         .eq("subject_id", record["subject_id"])\
                         .execute()
            if enrolled.data:
                return False, "أنت مسجل في هذه المادة مسبقاً"

            # Enroll student
            sb.table("enrollments").insert({
                "student_id":     student_id,
                "subject_id":     record["subject_id"],
                "access_code_id": record["id"],
            }).execute()

            # Increment use count
            sb.table("access_codes").update({
                "uses_count": record["uses_count"] + 1
            }).eq("id", record["id"]).execute()

            # Audit log
            sb.table("audit_logs").insert({
                "user_id":   student_id,
                "action":    "activate_code",
                "entity":    "access_code",
                "entity_id": record["id"],
                "metadata":  {"subject_id": record["subject_id"], "code": code}
            }).execute()

            return True, "✅ تم تفعيل الكود! يمكنك الوصول للمادة الآن"

        except AccessCodeError:
            raise
        except Exception as e:
            return False, f"خطأ في تفعيل الكود: {e}"

    # ─────────────────────────────────────────────────────────
    # GET BATCH CODES
    # ─────────────────────────────────────────────────────────
    def get_batch_codes(self, batch_id: str) -> list[dict]:
        try:
            sb = get_supabase_admin()
            res = sb.table("access_codes")\
                    .select("*")\
                    .eq("batch_id", batch_id)\
                    .order("created_at").execute()
            return res.data or []
        except Exception:
            return []

    def get_subject_batches(self, subject_id: str) -> list[dict]:
        try:
            sb = get_supabase_admin()
            res = sb.table("code_batches")\
                    .select("*")\
                    .eq("subject_id", subject_id)\
                    .order("created_at", desc=True).execute()
            return res.data or []
        except Exception:
            return []

    def get_batch_analytics(self, batch_id: str) -> dict:
        codes = self.get_batch_codes(batch_id)
        if not codes:
            return {}
        total    = len(codes)
        used     = sum(1 for c in codes if c["uses_count"] >= c["max_uses"])
        inactive = sum(1 for c in codes if not c["is_active"])
        now      = datetime.utcnow()
        expired  = sum(1 for c in codes if c["expires_at"] and
                       datetime.fromisoformat(c["expires_at"].replace("Z","")) < now)
        return {
            "total":           total,
            "used":            used,
            "unused":          total - used - expired - inactive,
            "expired":         expired,
            "inactive":        inactive,
            "redemption_rate": round(used / total * 100, 1) if total else 0,
        }
