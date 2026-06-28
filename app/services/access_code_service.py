from __future__ import annotations
import secrets
import string
from datetime import datetime, timezone
from app.core.security import get_supabase_admin
from app.core.exceptions import AccessCodeError


class AccessCodeService:

    # ─────────────────────────────────────────────────────────
    # CREATE BATCH  (PERF-01: bulk INSERT, no N+1)
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

            # Generate all codes in Python first (no DB round-trips)
            # UNIQUE constraint in DB is the final safety net
            chars    = string.ascii_uppercase + string.digits
            code_set = set()
            while len(code_set) < quantity:
                code_set.add("".join(secrets.choice(chars) for _ in range(8)))

            codes_to_insert = [
                {
                    "batch_id":   batch["id"],
                    "subject_id": subject_id,
                    "code":       code,
                    "max_uses":   max_uses,
                    "expires_at": str(expires_at) if expires_at else None,
                }
                for code in code_set
            ]

            # Single bulk INSERT (was 500+ sequential calls before)
            codes_res = sb.table("access_codes").insert(codes_to_insert).execute()

            sb.table("audit_logs").insert({
                "user_id":   created_by,
                "action":    "create_batch",
                "entity":    "code_batch",
                "entity_id": batch["id"],
                "metadata":  {
                    "quantity":    quantity,
                    "subject_id":  subject_id,
                    "batch_name":  batch_name,
                },
            }).execute()

            return {"batch": batch, "codes": codes_res.data}

        except Exception as e:
            raise AccessCodeError(f"خطأ في إنشاء الباتش: {e}")

    # ─────────────────────────────────────────────────────────
    # ACTIVATE CODE  (FIX-04: atomic via Postgres RPC)
    # ─────────────────────────────────────────────────────────
    def activate_code(self, student_id: str, code: str) -> tuple[bool, str, dict]:
        """
        Calls redeem_code_for_credits() — atomic RPC that:
        1. Validates the code (FOR UPDATE SKIP LOCKED)
        2. Enrolls student if first time
        3. Adds credits to subject wallet
        4. Logs audit trail
        Returns (ok, message, data_dict).
        """
        try:
            result = get_supabase_admin().rpc("redeem_code_for_credits", {
                "p_student_id": student_id,
                "p_code":       code.strip().upper(),
            }).execute()
            data = result.data or {}
            return data.get("ok", False), data.get("msg", "خطأ غير معروف"), data
        except Exception as e:
            return False, f"خطأ في تفعيل الكود: {e}", {}

    # ─────────────────────────────────────────────────────────
    # READ HELPERS
    # ─────────────────────────────────────────────────────────
    def get_batch_codes(self, batch_id: str) -> list[dict]:
        try:
            return get_supabase_admin() \
                .table("access_codes") \
                .select("*") \
                .eq("batch_id", batch_id) \
                .order("created_at") \
                .execute().data or []
        except Exception:
            return []

    def get_subject_batches(self, subject_id: str) -> list[dict]:
        try:
            return get_supabase_admin() \
                .table("code_batches") \
                .select("*") \
                .eq("subject_id", subject_id) \
                .order("created_at", desc=True) \
                .execute().data or []
        except Exception:
            return []

    def get_batch_analytics(self, batch_id: str) -> dict:
        codes = self.get_batch_codes(batch_id)
        if not codes:
            return {}
        total    = len(codes)
        now      = datetime.now(timezone.utc)
        used     = sum(1 for c in codes if c["uses_count"] >= c["max_uses"])
        inactive = sum(1 for c in codes if not c["is_active"])
        expired  = sum(
            1 for c in codes
            if c["expires_at"] and
               datetime.fromisoformat(c["expires_at"].replace("Z", "+00:00")) < now
        )
        return {
            "total":           total,
            "used":            used,
            "unused":          max(0, total - used - expired - inactive),
            "expired":         expired,
            "inactive":        inactive,
            "redemption_rate": round(used / total * 100, 1) if total else 0,
        }
