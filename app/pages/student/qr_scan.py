"""
Student QR Scan Page
Student pastes/types the token from the QR or opens the URL directly.
"""
from __future__ import annotations
import streamlit as st
from app.core.security import get_current_user_id
from app.services.qr_attendance_service import QRAttendanceService


def show_qr_scan():
    lang = st.session_state.get("lang", "ar")
    uid  = get_current_user_id()
    svc  = QRAttendanceService()

    st.title("📱 " + ("تسجيل الحضور بـ QR" if lang == "ar" else "QR Check-in"))

    # ── Check if token came via URL param ─────────────────────
    params = st.query_params
    url_token = params.get("attend", "")

    if url_token:
        # Auto-submit if opened from QR link
        st.info(f"📲 تم اكتشاف رمز QR — جاري التحقق...")
        _do_checkin(svc, uid, url_token)
        # Clear the param so refresh doesn't re-submit
        st.query_params.clear()
        return

    # ── Manual token entry ────────────────────────────────────
    st.markdown("""
    ### كيفية تسجيل الحضور
    1. اطلب من المعلم رؤية شاشة الـ QR
    2. افتح كاميرا هاتفك وامسح الكود
    3. أو أدخل الرمز يدوياً أدناه
    """)

    token = st.text_input(
        "🔑 أدخل رمز الحضور" if lang == "ar" else "Enter attendance token",
        placeholder="e.g. ABC123XY",
        key="qr_token_input"
    ).strip()

    if st.button("✅ تسجيل الحضور", type="primary",
                  use_container_width=True, disabled=not token):
        _do_checkin(svc, uid, token)


def _do_checkin(svc: QRAttendanceService, uid: str, token: str):
    with st.spinner("جاري التحقق..."):
        ok, msg = svc.verify_and_attend(uid, token)
    if ok:
        st.success(msg)
        st.balloons()
    else:
        st.error(msg)
