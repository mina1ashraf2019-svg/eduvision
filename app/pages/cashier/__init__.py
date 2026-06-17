import streamlit as st
from app.services.sales_service import SalesService


def show_cashier():
    sales = SalesService()
    user = st.session_state.user
    lang = user.get("language", "ar")

    st.title("🏦 " + ("بوابة الكاشير" if lang == "ar" else "Cashier Portal"))
    st.divider()

    tab1, tab2, tab3 = st.tabs([
        "📋 " + ("الفواتير" if lang == "ar" else "Invoices"),
        "➕ " + ("فاتورة جديدة" if lang == "ar" else "New Invoice"),
        "📊 " + ("التقارير" if lang == "ar" else "Reports"),
    ])

    with tab1:
        _show_invoices(sales, lang, user)

    with tab2:
        _show_new_invoice(sales, lang, user)

    with tab3:
        _show_reports(sales, lang)


def _show_invoices(sales, lang, user):
    st.subheader("📋 " + ("جدول الفواتير" if lang == "ar" else "Invoices"))

    col1, col2 = st.columns(2)
    with col1:
        search = st.text_input("🔍 " + ("بحث باسم الطالب" if lang == "ar" else "Search student"))
    with col2:
        status_filter = st.selectbox(
            "الحالة" if lang == "ar" else "Status",
            ["الكل", "paid", "pending", "refunded"]
        )

    records = sales.get_all_sales(
        search=search or None,
        status=None if status_filter == "الكل" else status_filter,
    )

    if not records:
        st.info("لا توجد فواتير." if lang == "ar" else "No invoices found.")
        return

    for rec in records:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])

            with c1:
                st.markdown(f"**👤 {rec.get('student_name', '—')}**")
                st.caption(f"📄 {rec.get('invoice_number', '—')}")

            with c2:
                st.markdown(f"💰 **{rec.get('total_amount', 0):,.0f} ج.م**")
                if rec.get("discount_pct", 0) > 0:
                    st.caption(f"خصم {rec['discount_pct']}%")

            with c3:
                status = rec.get("status", "pending")
                color = {"paid": "🟢", "pending": "🟡", "refunded": "🔴"}.get(status, "⚪")
                st.markdown(f"{color} {status}")
                st.caption(rec.get("payment_method", "—"))

            with c4:
                st.caption(str(rec.get("created_at", ""))[:10])

            with c5:
                # زرار فاتورة PDF
                if st.button("🧾 فاتورة", key=f"inv_{rec['id']}"):
                    st.session_state["invoice_data"] = rec
                    st.session_state["page"] = "invoice"
                    st.rerun()

                # زرار رد
                if status == "paid":
                    if st.button("🔁 رد", key=f"refund_{rec['id']}"):
                        st.session_state[f"confirm_refund_{rec['id']}"] = True

                    if st.session_state.get(f"confirm_refund_{rec['id']}"):
                        reason = st.text_input(
                            "سبب الرد" if lang == "ar" else "Refund reason",
                            key=f"reason_{rec['id']}"
                        )
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ تأكيد", key=f"yes_{rec['id']}"):
                                ok = sales.refund_sale(
                                    sale_id=rec["id"],
                                    reason=reason,
                                    refunded_by=st.session_state.user["id"]
                                )
                                if ok:
                                    st.success("تم الرد ✅")
                                    st.session_state.pop(f"confirm_refund_{rec['id']}", None)
                                    st.rerun()
                        with col_no:
                            if st.button("❌ إلغاء", key=f"no_{rec['id']}"):
                                st.session_state.pop(f"confirm_refund_{rec['id']}", None)
                                st.rerun()


def _show_new_invoice(sales, lang, user):
    st.subheader("➕ " + ("فاتورة جديدة" if lang == "ar" else "New Invoice"))

    students = sales.get_all_students()
    if not students:
        st.warning("لا يوجد طلاب مسجلين." if lang == "ar" else "No students registered.")
        return

    student_map = {f"{s['full_name']} — {s.get('phone', '')}": s for s in students}

    selected_label = st.selectbox(
        "👤 " + ("الطالب" if lang == "ar" else "Student"),
        list(student_map.keys())
    )
    selected_student = student_map[selected_label]

    col1, col2 = st.columns(2)
    with col1:
        subtotal = st.number_input(
            "💰 " + ("المبلغ الأساسي (ج.م)" if lang == "ar" else "Subtotal (EGP)"),
            min_value=0.0, step=50.0, format="%.2f"
        )
    with col2:
        discount_pct = st.number_input(
            "🏷️ " + ("نسبة الخصم %" if lang == "ar" else "Discount %"),
            min_value=0.0, max_value=100.0, step=5.0, format="%.1f"
        )

    discount_amount = round(subtotal * discount_pct / 100, 2)
    total = round(subtotal - discount_amount, 2)

    if discount_pct > 0:
        st.info(f"💡 خصم: {discount_amount:,.2f} ج.م | **الإجمالي: {total:,.2f} ج.م**")
    else:
        st.info(f"💡 **الإجمالي: {total:,.2f} ج.م**")

    payment_method = st.selectbox(
        "💳 " + ("طريقة الدفع" if lang == "ar" else "Payment Method"),
        ["cash", "vodafone_cash", "instapay", "bank_transfer"]
    )
    notes = st.text_area("📝 " + ("ملاحظات" if lang == "ar" else "Notes"), height=80)

    if st.button(
        "✅ " + ("تسجيل الفاتورة" if lang == "ar" else "Register Invoice"),
        use_container_width=True, type="primary"
    ):
        if subtotal <= 0:
            st.error("المبلغ يجب أن يكون أكبر من صفر." if lang == "ar" else "Amount must be > 0.")
        else:
            ok, inv_num = sales.create_sale(
                student_id=selected_student["id"],
                student_name=selected_student["full_name"],
                student_phone=selected_student.get("phone", ""),
                subtotal=subtotal,
                discount_pct=discount_pct,
                payment_method=payment_method,
                notes=notes,
                cashier_id=user["id"]
            )
            if ok:
                st.success(f"✅ تم تسجيل الفاتورة: **{inv_num}**")
                st.balloons()
            else:
                st.error("فشل تسجيل الفاتورة." if lang == "ar" else "Failed to register invoice.")


def _show_reports(sales, lang):
    st.subheader("📊 " + ("تقرير المبيعات" if lang == "ar" else "Sales Report"))

    summary = sales.get_summary()
    if not summary:
        st.info("لا توجد بيانات." if lang == "ar" else "No data.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 الإجمالي", f"{summary.get('total', 0):,.0f} ج.م")
    c2.metric("🟢 مدفوع", f"{summary.get('paid', 0):,.0f} ج.م")
    c3.metric("🟡 معلق", f"{summary.get('pending', 0):,.0f} ج.م")
    c4.metric("🔴 مردود", f"{summary.get('refunded', 0):,.0f} ج.م")

    st.divider()

    by_month = sales.get_sales_by_month()
    if by_month:
        st.subheader("📅 " + ("الإيراد الشهري" if lang == "ar" else "Monthly Revenue"))
        import pandas as pd
        df = pd.DataFrame(by_month)
        st.bar_chart(df.set_index("الشهر"))
