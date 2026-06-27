from app.core.security import get_supabase, get_supabase_admin
import streamlit as st
from datetime import datetime
import uuid


class SalesService:
    def __init__(self):
        self.db = get_supabase()

    # ── Read ──────────────────────────────────────────────────

    def get_all_sales(self, search=None, status=None):
        try:
            q = (
                self.db.table("sales_invoices")
                .select("*")
                .order("created_at", desc=True)
            )
            if status:
                q = q.eq("status", status)

            res = q.execute()
            rows = res.data or []

            if search:
                rows = [r for r in rows if search.lower() in (r.get("student_name") or "").lower()]

            return rows
        except Exception as e:
            st.error(f"خطأ في جلب المبيعات: {e}")
            return []

    def get_all_students(self):
        try:
            res = (
                self.db.table("users")
                .select("id, full_name, phone")
                .eq("role", "student")
                .order("full_name")
                .execute()
            )
            return res.data or []
        except Exception as e:
            st.error(f"خطأ في جلب الطلاب: {e}")
            return []

    def get_summary(self):
        try:
            res = self.db.table("sales_invoices").select("total_amount, status").execute()
            rows = res.data or []
            total = sum(r["total_amount"] for r in rows)
            paid = sum(r["total_amount"] for r in rows if r["status"] == "paid")
            pending = sum(r["total_amount"] for r in rows if r["status"] == "pending")
            refunded = sum(r["total_amount"] for r in rows if r["status"] == "refunded")
            return {"total": total, "paid": paid, "pending": pending, "refunded": refunded}
        except Exception as e:
            st.error(f"خطأ في التقرير: {e}")
            return {}

    def get_sales_by_month(self):
        try:
            res = (
                self.db.table("sales_invoices")
                .select("total_amount, status, created_at")
                .eq("status", "paid")
                .execute()
            )
            rows = res.data or []
            agg = {}
            for r in rows:
                month = str(r.get("created_at", ""))[:7]  # YYYY-MM
                agg[month] = agg.get(month, 0) + r["total_amount"]
            return [{"الشهر": k, "الإيراد": v} for k, v in sorted(agg.items())]
        except Exception as e:
            st.error(f"خطأ في التجميع: {e}")
            return []

    # ── Write ─────────────────────────────────────────────────

    def create_sale(self, student_id, student_name, student_phone,
                    subtotal, discount_pct, payment_method, notes, cashier_id):
        try:
            discount_amount = round(subtotal * discount_pct / 100, 2)
            total_amount = round(subtotal - discount_amount, 2)
            invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            self.db.table("sales_invoices").insert({
                "id": str(uuid.uuid4()),
                "invoice_number": invoice_number,
                "cashier_id": cashier_id,
                "student_id": student_id,
                "student_name": student_name,
                "student_phone": student_phone or "",
                "subtotal": subtotal,
                "discount_pct": discount_pct,
                "discount_amount": discount_amount,
                "total_amount": total_amount,
                "payment_method": payment_method,
                "status": "paid",
                "notes": notes or "",
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            return True, invoice_number
        except Exception as e:
            st.error(f"خطأ في إنشاء الفاتورة: {e}")
            return False, None

    def refund_sale(self, sale_id, reason, refunded_by):
        try:
            self.db.table("sales_invoices").update({
                "status": "refunded",
                "refunded_by": refunded_by,
                "refunded_at": datetime.utcnow().isoformat(),
                "refund_reason": reason,
            }).eq("id", sale_id).execute()
            return True
        except Exception as e:
            st.error(f"خطأ في الرد: {e}")
            return False

    def get_today_revenue(self) -> dict:
        """Returns today's revenue and invoice count."""
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            res = self.db.table("sales_invoices") \
                         .select("total_amount, status") \
                         .eq("status", "paid") \
                         .gte("created_at", f"{today}T00:00:00") \
                         .lte("created_at", f"{today}T23:59:59") \
                         .execute()
            rows = res.data or []
            return {
                "revenue":  round(sum(r["total_amount"] for r in rows), 2),
                "invoices": len(rows),
            }
        except Exception:
            return {"revenue": 0, "invoices": 0}

    def get_invoices(self, limit: int = 100) -> list:
        """Returns latest invoices."""
        try:
            res = self.db.table("sales_invoices") \
                         .select("*") \
                         .order("created_at", desc=True) \
                         .limit(limit) \
                         .execute()
            return res.data or []
        except Exception:
            return []

    def create_invoice(self, cashier_id: str, items: list,
                       student_name: str, student_phone: str,
                       discount_pct: float, payment_method: str,
                       notes: str = "") -> dict:
        """Creates an invoice from a list of items."""
        try:
            subtotal        = sum(i["quantity"] * i["unit_price"] for i in items)
            discount_amount = round(subtotal * discount_pct / 100, 2)
            total_amount    = round(subtotal - discount_amount, 2)
            invoice_number  = f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            res = self.db.table("sales_invoices").insert({
                "id":              str(uuid.uuid4()),
                "invoice_number":  invoice_number,
                "cashier_id":      cashier_id,
                "student_name":    student_name,
                "student_phone":   student_phone or "",
                "subtotal":        subtotal,
                "discount_pct":    discount_pct,
                "discount_amount": discount_amount,
                "total_amount":    total_amount,
                "payment_method":  payment_method,
                "status":          "paid",
                "notes":           notes,
                "created_at":      datetime.utcnow().isoformat(),
            }).execute()

            return res.data[0] if res.data else {"invoice_number": invoice_number}
        except Exception as e:
            raise Exception(f"خطأ في إنشاء الفاتورة: {e}")
