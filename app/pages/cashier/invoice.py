import streamlit as st
from app.reports.pdf_exporter import generate_invoice_pdf


def show_invoice():
    invoice = st.session_state.get("invoice_data")
    user = st.session_state.get("user", {})
    lang = user.get("language", "ar")

    if not invoice:
        st.warning("لا توجد فاتورة محددة." if lang == "ar" else "No invoice selected.")
        if st.button("🔙 رجوع"):
            st.session_state.pop("page", None)
            st.rerun()
        return

    # ── Back button ───────────────────────────────────────────
    if st.button("🔙 " + ("رجوع للفواتير" if lang == "ar" else "Back to Invoices")):
        st.session_state.pop("page", None)
        st.session_state.pop("invoice_data", None)
        st.rerun()

    st.title("🧾 " + ("الفاتورة" if lang == "ar" else "Invoice"))
    st.divider()

    # ── Invoice preview ───────────────────────────────────────
    status = invoice.get("status", "paid")
    status_color = {"paid": "🟢", "pending": "🟡", "refunded": "🔴"}.get(status, "⚪")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**📄 رقم الفاتورة:** `{invoice.get('invoice_number', '—')}`")
        st.markdown(f"**👤 الطالب:** {invoice.get('student_name', '—')}")
        st.markdown(f"**📞 الهاتف:** {invoice.get('student_phone', '—')}")
        st.markdown(f"**📅 التاريخ:** {str(invoice.get('created_at', ''))[:10]}")

    with col2:
        st.markdown(f"**الحالة:** {status_color} {status}")
        st.markdown(f"**💳 طريقة الدفع:** {invoice.get('payment_method', '—')}")
        st.markdown(f"**💰 المبلغ الأساسي:** {invoice.get('subtotal', 0):,.2f} ج.م")
        if invoice.get("discount_pct", 0) > 0:
            st.markdown(f"**🏷️ الخصم:** {invoice.get('discount_pct', 0):.0f}% "
                        f"(— {invoice.get('discount_amount', 0):,.2f} ج.م)")

    st.divider()

    # Total
    total = invoice.get("total_amount", 0)
    st.markdown(
        f"<div style='background:#0F2D6B;color:white;padding:12px 20px;"
        f"border-radius:8px;font-size:18px;font-weight:bold;text-align:center;'>"
        f"الإجمالي: {total:,.2f} ج.م</div>",
        unsafe_allow_html=True
    )

    if invoice.get("notes"):
        st.info(f"📝 ملاحظات: {invoice['notes']}")

    if status == "refunded" and invoice.get("refund_reason"):
        st.error(f"🔁 تم الرد — السبب: {invoice['refund_reason']}")

    st.divider()

    # ── PDF Download ──────────────────────────────────────────
    try:
        pdf_bytes = generate_invoice_pdf(invoice)
        filename = f"invoice_{invoice.get('invoice_number', 'eduvision')}.pdf"

        st.download_button(
            label="⬇️ " + ("تحميل الفاتورة PDF" if lang == "ar" else "Download Invoice PDF"),
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
        st.success("✅ الفاتورة جاهزة للتحميل — تحتوي على QR للتحقق" if lang == "ar"
                   else "Invoice ready — includes QR verification code")

    except Exception as e:
        st.error(f"خطأ في توليد الفاتورة: {e}")
