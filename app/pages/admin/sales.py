import streamlit as st
from app.core.security import get_supabase_admin, get_current_user_id
from app.services.sales_service import SalesService
from app.services.access_code_service import AccessCodeService
from translations import get_lang


def show_sales():
    lang = get_lang()
    uid  = get_current_user_id()
    sb   = get_supabase_admin()
    svc  = SalesService()

    st.title("💰 " + ("المبيعات والكاشير" if lang=="ar" else "Sales & Cashier"))

    # Revenue stats
    today_rev = svc.get_today_revenue()
    c1, c2 = st.columns(2)
    c1.metric("💰 إيرادات اليوم",    f"{today_rev['revenue']} ج.م")
    c2.metric("🧾 فواتير اليوم",     today_rev["invoices"])

    st.divider()
    tab1, tab2 = st.tabs(["🧾 إنشاء فاتورة", "📋 الفواتير"])

    # ── CREATE INVOICE ─────────────────────────────────────────
    with tab1:
        st.subheader("🧾 فاتورة جديدة")

        c1, c2 = st.columns(2)
        with c1:
            stu_name  = st.text_input("اسم الطالب")
            stu_phone = st.text_input("رقم الهاتف")
        with c2:
            pay_method  = st.selectbox("طريقة الدفع", ["cash","card","transfer"])
            discount    = st.number_input("خصم %", 0.0, 100.0, 0.0)

        st.markdown("**إضافة مواد:**")

        # Load subjects + batches
        try:
            subs = sb.table("subjects").select("id, name_ar").eq("is_active", True).execute().data or []
        except Exception:
            subs = []

        sub_opts = {s["name_ar"]: s["id"] for s in subs}
        items    = []

        if "invoice_items" not in st.session_state:
            st.session_state.invoice_items = []

        chosen_sub = st.selectbox("اختر المادة", list(sub_opts.keys()), key="inv_sub")
        if chosen_sub:
            sub_id = sub_opts[chosen_sub]
            try:
                batches = sb.table("code_batches").select("id, batch_name")\
                            .eq("subject_id", sub_id).execute().data or []
                batch_opts = {b["batch_name"]: b["id"] for b in batches}
            except Exception:
                batch_opts = {}

            c1, c2, c3 = st.columns(3)
            with c1:
                chosen_batch = st.selectbox("الباتش", list(batch_opts.keys()), key="inv_batch") \
                               if batch_opts else None
            with c2:
                qty   = st.number_input("الكمية", 1, 100, 1, key="inv_qty")
            with c3:
                price = st.number_input("السعر للوحدة", 0.0, 9999.0, 0.0, key="inv_price")

            if st.button("➕ إضافة للفاتورة"):
                st.session_state.invoice_items.append({
                    "subject_id":   sub_id,
                    "subject_name": chosen_sub,
                    "batch_id":     batch_opts.get(chosen_batch) if chosen_batch else None,
                    "quantity":     int(qty),
                    "unit_price":   float(price),
                })
                st.rerun()

        # Show current items
        if st.session_state.invoice_items:
            st.markdown("**عناصر الفاتورة:**")
            total = 0
            for i, item in enumerate(st.session_state.invoice_items):
                line = item["quantity"] * item["unit_price"]
                total += line
                c1, c2 = st.columns([5, 1])
                c1.markdown(f"• {item['subject_name']} × {item['quantity']} × {item['unit_price']} = **{line} ج.م**")
                if c2.button("🗑️", key=f"rm_item_{i}"):
                    st.session_state.invoice_items.pop(i)
                    st.rerun()

            disc_amount = round(total * discount / 100, 2)
            final = round(total - disc_amount, 2)
            st.markdown(f"**الإجمالي:** {total} ج.م")
            if discount > 0:
                st.markdown(f"**الخصم ({discount}%):** -{disc_amount} ج.م")
            st.markdown(f"### المجموع النهائي: {final} ج.م")

            if st.button("✅ إصدار الفاتورة", type="primary", use_container_width=True):
                if not stu_name:
                    st.error("أدخل اسم الطالب")
                else:
                    try:
                        invoice = svc.create_invoice(
                            cashier_id=uid,
                            items=st.session_state.invoice_items,
                            student_name=stu_name,
                            student_phone=stu_phone,
                            discount_pct=float(discount),
                            payment_method=pay_method,
                        )
                        st.success(f"✅ تم إصدار الفاتورة: {invoice['invoice_number']}")
                        st.session_state.invoice_items = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"خطأ: {e}")

    # ── INVOICES LIST ──────────────────────────────────────────
    with tab2:
        invoices = svc.get_invoices()
        if invoices:
            import pandas as pd
            df = pd.DataFrame([{
                "رقم الفاتورة": i["invoice_number"],
                "الطالب":       i.get("student_name") or (i.get("profiles") or {}).get("full_name","—"),
                "الإجمالي":     f"{i['total_amount']} ج.م",
                "الدفع":        i["payment_method"],
                "الحالة":       {"paid":"✅ مدفوع","refunded":"↩️ مسترجع","cancelled":"❌ ملغي"}.get(i["status"],i["status"]),
                "التاريخ":      str(i["created_at"])[:10],
            } for i in invoices])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد فواتير بعد.")
