from __future__ import annotations
from app.core.security import get_supabase, get_supabase_admin


class CreditService:

    # ─────────────────────────────────────────────────────────
    # WALLET
    # ─────────────────────────────────────────────────────────
    def get_wallet(self, student_id: str, subject_id: str) -> dict:
        try:
            res = get_supabase_admin() \
                .table("subject_credit_wallets") \
                .select("*") \
                .eq("student_id", student_id) \
                .eq("subject_id", subject_id) \
                .execute()
            return res.data[0] if res.data else {
                "credits_available": 0, "credits_used": 0
            }
        except Exception:
            return {"credits_available": 0, "credits_used": 0}

    def get_all_wallets_for_student(self, student_id: str) -> list[dict]:
        try:
            res = get_supabase_admin() \
                .table("subject_credit_wallets") \
                .select("*, subjects(name_ar)") \
                .eq("student_id", student_id) \
                .execute()
            return res.data or []
        except Exception:
            return []

    # ─────────────────────────────────────────────────────────
    # CONSUME CREDIT  (called when student opens a lecture)
    # ─────────────────────────────────────────────────────────
    def consume_lecture_credit(
        self, student_id: str, lecture_id: str, subject_id: str
    ) -> tuple[bool, str, dict]:
        """
        Returns (ok, message, data).
        Calls the atomic Postgres RPC.
        Re-access is free (handled in RPC via lecture_access_log).
        """
        try:
            result = get_supabase_admin().rpc("consume_lecture_credit", {
                "p_student_id": student_id,
                "p_lecture_id": lecture_id,
                "p_subject_id": subject_id,
            }).execute()
            data = result.data or {}
            return data.get("ok", False), data.get("msg", "خطأ"), data
        except Exception as e:
            return False, f"خطأ في التحقق من الرصيد: {e}", {}

    # ─────────────────────────────────────────────────────────
    # TRANSACTIONS HISTORY
    # ─────────────────────────────────────────────────────────
    def get_transactions(
        self, student_id: str, subject_id: str | None = None,
        limit: int = 50
    ) -> list[dict]:
        try:
            q = get_supabase_admin() \
                .table("credit_transactions") \
                .select("*, subjects(name_ar), lectures(title_ar)") \
                .eq("student_id", student_id) \
                .order("created_at", desc=True) \
                .limit(limit)
            if subject_id:
                q = q.eq("subject_id", subject_id)
            return q.execute().data or []
        except Exception:
            return []

    # ─────────────────────────────────────────────────────────
    # MANUAL ADJUSTMENT (admin/owner)
    # ─────────────────────────────────────────────────────────
    def adjust_credits(
        self, admin_id: str, student_id: str,
        subject_id: str, amount: int, reason: str
    ) -> tuple[bool, str]:
        try:
            result = get_supabase_admin().rpc("adjust_student_credits", {
                "p_admin_id":   admin_id,
                "p_student_id": student_id,
                "p_subject_id": subject_id,
                "p_amount":     amount,
                "p_reason":     reason,
            }).execute()
            data = result.data or {}
            return data.get("ok", False), str(data.get("new_balance", ""))
        except Exception as e:
            return False, str(e)

    # ─────────────────────────────────────────────────────────
    # ANALYTICS (admin/owner)
    # ─────────────────────────────────────────────────────────
    def get_subject_credit_stats(self, subject_id: str) -> dict:
        try:
            sb = get_supabase_admin()
            wallets = sb.table("subject_credit_wallets") \
                        .select("credits_available, credits_used") \
                        .eq("subject_id", subject_id).execute().data or []
            txns = sb.table("credit_transactions") \
                     .select("type, amount") \
                     .eq("subject_id", subject_id).execute().data or []
            total_issued = sum(t["amount"] for t in txns if t["type"] == "credit")
            total_used   = sum(t["amount"] for t in txns if t["type"] == "debit")
            total_avail  = sum(w["credits_available"] for w in wallets)
            return {
                "total_issued":  total_issued,
                "total_used":    total_used,
                "total_available": total_avail,
                "active_wallets": len(wallets),
            }
        except Exception:
            return {}

    def get_student_credit_summary(self, student_id: str) -> list[dict]:
        """Returns per-subject credit summary for a student."""
        return self.get_all_wallets_for_student(student_id)
