"""
Teacher QR Attendance Page
Shows a live QR code → students scan → list updates every 5 seconds
"""
from __future__ import annotations
import io
import time
import qrcode
import streamlit as st
from datetime import datetime, timezone
from app.core.security import get_supabase_admin, get_current_user_id
from app.services.qr_attendance_service import QRAttendanceService


def show_qr_attendance():
    lang = st.session_state.get("lang", "ar")
    uid  = get_current_user_id()
    sb   = get_supabase_admin()
    svc  = QRAttendanceService()

    st.title("📱 " + ("حضور QR" if lang == "ar" else "QR Attendance"))

    # ── Subject selector ──────────────────────────────────────
    try:
        # Teacher sees only their subjects
        enroll = sb.table("subjects") \
                   .select("id, name_ar") \
                   .eq("is_active", True) \
                   .execute().data or []
    except Exception:
        enroll = []

    if not enroll:
        st.info("لا توجد مواد متاحة.")
        return

    sub_map  = {s["name_ar"]: s["id"] for s in enroll}
    chosen   = st.selectbox("📚 اختر المادة", list(sub_map.keys()), key="qr_sub")
    subj_id  = sub_map[chosen]

    st.divider()

    # ── Check active session ──────────────────────────────────
    active = svc.get_active_session(subj_id)

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        # ── QR panel ─────────────────────────────────────────
        if active:
            left_secs = svc.session_time_left(active)

            if left_secs > 0:
                st.success(f"✅ جلسة نشطة — تنتهي بعد **{left_secs // 60}:{left_secs % 60:02d}** دقيقة")

                # Build QR content — a URL the student opens
                # In production replace with your real domain
                base_url = st.secrets.get("app", {}).get(
                    "base_url", "https://eduvision.streamlit.app")
                qr_content = f"{base_url}/?attend={active['token']}"

                # Generate QR image
                qr_img = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=8,
                    border=3,
                )
                qr_img.add_data(qr_content)
                qr_img.make(fit=True)
                img = qr_img.make_image(fill_color="#0F2D6B", back_color="white")

                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)

                st.image(buf, caption="اطلب من الطلاب مسح الكود", use_container_width=True)
                st.caption(f"🔗 Token: `{active['token'][:16]}...`")

                # Progress bar for time
                progress = left_secs / (QRAttendanceService.SESSION_DURATION_MINUTES * 60)
                st.progress(progress)

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🔄 تجديد الـ QR", use_container_width=True):
                        svc.create_session(uid, subj_id)
                        st.rerun()
                with col_b:
                    if st.button("⛔ إنهاء الجلسة", use_container_width=True, type="secondary"):
                        svc.close_session(active["id"])
                        st.success("تم إنهاء الجلسة")
                        st.rerun()
            else:
                st.warning("⏰ انتهت الجلسة")
                _show_start_button(svc, uid, subj_id)
        else:
            _show_start_button(svc, uid, subj_id)

    with col_right:
        # ── Live attendees list ───────────────────────────────
        attendees = svc.get_session_attendees(subj_id)

        st.subheader(f"👥 الحاضرون ({len(attendees)})")

        if not attendees:
            st.info("لم يسجل أحد بعد.")
        else:
            for i, a in enumerate(attendees, 1):
                name   = (a.get("profiles") or {}).get("full_name", "—")
                status = a.get("status", "present")
                time_s = str(a.get("check_in_at", ""))[:19].replace("T", " ")
                icon   = "✅" if status == "present" else "🕐"
                st.markdown(
                    f"`{i:02}` {icon} **{name}** "
                    f"<span style='color:#6B7280;font-size:11px'>{time_s}</span>",
                    unsafe_allow_html=True
                )

        # Auto-refresh every 5 seconds while session is active
        if active and svc.session_time_left(active) > 0:
            st.caption("🔄 يتحدث تلقائياً كل 5 ثواني")
            time.sleep(5)
            st.rerun()


def _show_start_button(svc, uid, subj_id):
    st.info("لا توجد جلسة QR نشطة الآن.")
    duration = st.slider("⏱️ مدة الجلسة (دقائق)", 2, 30, 5, key="qr_dur")
    if st.button("▶️ بدء جلسة QR", type="primary", use_container_width=True):
        svc.create_session(uid, subj_id, minutes=duration)
        st.rerun()
