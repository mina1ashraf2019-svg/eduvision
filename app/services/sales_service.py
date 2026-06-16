from __future__ import annotations
from datetime import datetime
from app.core.security import get_supabase, get_supabase_admin


class SalesService:

    def create_invoice(self, cashier_id: str, items: list[dict],
                       student_id: str = None, student_name: str = "",
                       student_phone: str = "", discount_pct: float = 0,
                       payment_method: str = "cash", notes: str = "") -> dict:
        """
        items = [{"subject_id", "subject_name", "batch_id", "quantity", "unit_price"}]
        """
        sb = get_supabase_admin()

        subtotal = sum(i["quantity"] * i["unit_price"] for i in items)
        discount_amount = round(subtotal * discount_pct / 100, 2)
        total = round(subtotal - discount_amount, 2)

        # Create invoice
        inv_res = sb.table("sales_invoices").insert({
            "invoice_number":  "",   # trigger fills this
            "cashier_id":      cashier_id,
            "student_id":      student_id,
            "student_name":    student_name,
            "student_phone":   student_phone,
            "subtotal":        subtotal,
            "discount_pct":    discount_pct,
            "discount_amount": discount_amount,
            "total_amount":    total,
            "payment_method":  payment_method,
            "status":          "paid",
            "notes":           notes,
        }).execute()
        invoice = inv_res.data[0]

        # Insert items
        for item in items:
            item_res = sb.table("invoice_items").insert({
                "invoice_id":   invoice["id"],
                "subject_id":   item.get("subject_id"),
                "subject_name": item["subject_name"],
                "batch_id":     item.get("batch_id"),
                "quantity":     item["quantity"],
                "unit_price":   item["unit_price"],
                "total_price":  item["quantity"] * item["unit_price"],
            }).execute()

        # Audit log
        sb.table("audit_logs").insert({
            "user_id":   cashier_id,
            "action":    "invoice_created",
            "entity":    "invoice",
            "entity_id": invoice["id"],
            "metadata":  {"total": total, "items": len(items)}
        }).execute()

        return invoice

    def get_today_revenue(self) -> dict:
        try:
            sb = get_supabase_admin()
            today = datetime.utcnow().date().isoformat()
            res = sb.table("sales_invoices")\
                    .select("total_amount, status")\
                    .gte("created_at", today)\
                    .eq("status", "paid").execute()
            rows = res.data or []
            return {
                "revenue":  round(sum(r["total_amount"] for r in rows), 2),
                "invoices": len(rows),
            }
        except Exception:
            return {"revenue": 0, "invoices": 0}

    def get_invoices(self, limit: int = 100,
                     cashier_id: str = None) -> list[dict]:
        try:
            sb = get_supabase_admin()
            q = sb.table("sales_invoices")\
                  .select("*, profiles(full_name)")\
                  .order("created_at", desc=True).limit(limit)
            if cashier_id:
                q = q.eq("cashier_id", cashier_id)
            return q.execute().data or []
        except Exception:
            return []

    def refund_invoice(self, invoice_id: str, refunded_by: str,
                       reason: str = "") -> None:
        sb = get_supabase_admin()
        sb.table("sales_invoices").update({
            "status":        "refunded",
            "refunded_by":   refunded_by,
            "refunded_at":   datetime.utcnow().isoformat(),
            "refund_reason": reason,
        }).eq("id", invoice_id).execute()
        sb.table("audit_logs").insert({
            "user_id":   refunded_by,
            "action":    "invoice_refunded",
            "entity":    "invoice",
            "entity_id": invoice_id,
            "metadata":  {"reason": reason}
        }).execute()
