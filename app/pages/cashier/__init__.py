import streamlit as st
from app.core.security import get_supabase, get_current_user_id
from app.services.sales_service import SalesService
from translations import get_lang


def show_cashier():
    lang = get_lang()
    uid  = get_current_user_id()
    sb   = get_supabase()
    svc  = SalesService()

    with st.sidebar:
        st.markdown(f"### 💰 {'الكاشير' if lang=='ar' else 'Cashier'}")
        pages = {
            "new_invoice": ("🧾", "فاتورة جديدة"),
            "invoices":    ("📋", "الفواتير"),
        }
        if "cashier_page" not in st.session_state:
            st.session_state.cashier_page = "new_invoice"
        for key, (icon, label) in pages.items():
            active = st.session_state.cashier_page == key
            if st.button(f"{icon} {label}", use_container_width=True,
                         type="primary" if active else "secondary",
                         key=f"cash_nav_{key}"):
                st.session_state.cashier_page = key
                st.rerun()

    page = st.session_state.cashier_page
    if   page == "new_invoice": _new_invoice(sb, svc, uid, lang)
    elif page == "invoices":    _invoices(sb, svc, uid, lang)


def _new_invoice(sb, svc, uid, lang):
    st.title("🧾 فاتورة جديدة")

    # Revenue stats
    try:
        today_rev = svc.get_today_revenue()
        c1, c2 = st.columns(2)
        c1.metric("💰 إيرادات اليوم", f"{today_rev['revenue']} ج.م")
        c2.metric("🧾 فواتير اليوم",  today_rev["invoices"])
        st.divider()
    except Exception:
        pass

    c1, c2 = st.columns(2)
    with c1:
        stu_name  = st.text_input("اسم الطالب *")
        stu_phone = st.text_input("رقم الهاتف")
    with c2:
        pay_method = st.selectbox("طريقة الدفع", ["cash", "card", "transfer"])
        discount   = st.number_input("خصم %", 0.0, 100.0, 0.0)

    st.markdown("---")
    st.markdown("**➕ إضافة مادة للفاتورة**")

    try:
        subs = sb.table("subjects").select("id, name_ar").eq("is_active", True).execute().data or []
    except Exception:
        subs = []

    sub_opts = {s["name_ar"]: s["id"] for s in subs}

    if "cashier_items" not in st.session_state:
        st.session_state.cashier_items = []

    if sub_opts:
        chosen_sub = st.selectbox("اختر المادة", list(sub_opts.keys()), key="cash_sub")
        sub_id = sub_opts[chosen_sub]

        try:
            batches    = sb.table("code_batches").select("id, batch_name")\
                           .eq("subject_id", sub_id).execute().data or []
            batch_opts = {b["batch_name"]: b["id"] for b in batches}
        except Exception:
            batch_opts = {}

        c1, c2, c3 = st.columns(3)
        with c1:
            chosen_batch = st.selectbox("الباتش", list(batch_opts.keys()), key="cash_batch") \
                           if batch_opts else None
        with c2:
            qty = st.number_input("الكمية", 1, 100, 1, key="cash_qty")
        with c3:
            price = st.number_input("السعر/الوحدة (ج.م)", 0.0, 9999.0, 0.0, key="cash_price")

        if st.button("➕ إضافة للفاتورة", use_container_width=True):
            st.session_state.cashier_items.append({
                "subject_id":   sub_id,
                "subject_name": chosen_sub,
                "batch_id":     batch_opts.get(chosen_batch) if chosen_batch else None,
                "batch_name":   chosen_batch or "—",
                "quantity":     int(qty),
                "unit_price":   float(price),
            })
            st.rerun()

    st.markdown("---")

    if st.session_state.cashier_items:
        st.markdown("**📋 عناصر الفاتورة:**")
        total = 0
        for i, item in enumerate(st.session_state.cashier_items):
            line   = item["quantity"] * item["unit_price"]
            total += line
            c1, c2 = st.columns([6, 1])
            c1.markdown(f"• **{item['subject_name']}** × {item['quantity']} × {item['unit_price']} ج.م = **{line:.2f} ج.م**")
            if c2.button("🗑️", key=f"cash_rm_{i}"):
                st.session_state.cashier_items.pop(i)
                st.rerun()

        disc_amount = round(total * discount / 100, 2)
        final       = round(total - disc_amount, 2)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**الإجمالي قبل الخصم:** {total:.2f} ج.م")
            if discount > 0:
                st.markdown(f"**الخصم ({discount}%):** -{disc_amount:.2f} ج.م")
            st.markdown(f"## 💰 المجموع: {final:.2f} ج.م")
        with col2:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("✅ إصدار الفاتورة", type="primary", use_container_width=True):
                if not stu_name:
                    st.error("أدخل اسم الطالب")
                else:
                    try:
                        invoice = svc.create_invoice(
                            cashier_id=uid,
                            items=st.session_state.cashier_items,
                            student_name=stu_name,
                            student_phone=stu_phone,
                            discount_pct=float(discount),
                            payment_method=pay_method,
                        )
                        inv_num = invoice["invoice_number"]
                        st.success(f"✅ تم إصدار الفاتورة: **{inv_num}**")
                        st.session_state.cashier_items = []

                        # PDF download button
                        try:
                            from app.reports.pdf_exporter import generate_invoice_pdf
                            pdf_buf = generate_invoice_pdf(invoice)
                            st.download_button(
                                "🖨️ طباعة / تحميل PDF",
                                data=pdf_buf,
                                file_name=f"invoice_{inv_num}.pdf",
                                mime="application/pdf",
                            )
                        except Exception as e:
                            st.warning(f"PDF غير متاح: {e}")

                        st.rerun()
                    except Exception as e:
                        st.error(f"خطأ: {e}")
    else:
        st.info("أضف مادة واحدة على الأقل للفاتورة.")


def _invoices(sb, svc, uid, lang):
    st.title("📋 الفواتير")

    try:
        invoices = svc.get_invoices(cashier_id=uid)
    except Exception:
        try:
            invoices = svc.get_invoices()
        except Exception as e:
            st.error(f"خطأ: {e}")
            return

    if not invoices:
        st.info("لا توجد فواتير بعد.")
        return

    for inv in invoices:
        inv_num    = inv.get("invoice_number", "—")
        stu        = inv.get("student_name") or (inv.get("profiles") or {}).get("full_name","—")
        total      = inv.get("total_amount", 0)
        status     = inv.get("status","paid")
        created_at = str(inv.get("created_at",""))[:10]
        status_map = {"paid":"✅ مدفوع","refunded":"↩️ مسترجع","cancelled":"❌ ملغي","pending":"⏳ معلق"}
        status_lbl = status_map.get(status, status)

        with st.expander(f"{status_lbl} | {inv_num} | {stu} | {total} ج.م | {created_at}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**الطالب:** {stu}")
                st.markdown(f"**طريقة الدفع:** {inv.get('payment_method','—')}")
                st.markdown(f"**الإجمالي:** {total} ج.م")
                if inv.get("discount_pct",0) > 0:
                    st.markdown(f"**الخصم:** {inv['discount_pct']}% (-{inv.get('discount_amount',0)} ج.م)")
                if inv.get("notes"):
                    st.caption(inv["notes"])
            with c2:
                # PDF export
                try:
                    from app.reports.pdf_exporter import generate_invoice_pdf
                    pdf_buf = generate_invoice_pdf(inv)
                    st.download_button(
                        "🖨️ PDF",
                        data=pdf_buf,
                        file_name=f"invoice_{inv_num}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{inv['id']}",
                    )
                except Exception:
                    pass
