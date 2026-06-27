from __future__ import annotations
import secrets
import hashlib
from datetime import datetime, timezone, timedelta, date
from app.core.security import get_supabase_admin


class QRAttendanceService:
    """
    Manages QR-based attendance sessions.
    Flow:
      Teacher → create_session() → gets token → shows QR
      Student → scan QR → verify_and_attend(token) → attendance recorded
      Teacher screen → get_session_attendees() → live list (via polling)
    """

    SESSION_DURATION_MINUTES = 5  # QR expires after 5 minutes

    # ─────────────────────────────────────────────────────────
    # TEACHER: create a new QR session
    # ─────────────────────────────────────────────────────────
    def create_session(self, teacher_id: str, subject_id: str,
                       lecture_id: str = None,
                       minutes: int = None) -> dict:
        """
        Creates a new QR session and deactivates any previous ones
        for the same subject. Returns the session dict with token.
        """
        sb = get_supabase_admin()
        duration = minutes or self.SESSION_DURATION_MINUTES

        # Deactivate old sessions for this subject
        sb.table("qr_sessions").update({"is_active": False}) \
          .eq("subject_id", subject_id) \
          .eq("is_active", True) \
          .execute()

        token      = secrets.token_urlsafe(24)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration)

        res = sb.table("qr_sessions").insert({
            "teacher_id": teacher_id,
            "subject_id": subject_id,
            "lecture_id": lecture_id,
            "token":      token,
            "expires_at": expires_at.isoformat(),
            "is_active":  True,
            "scan_count": 0,
        }).execute()

        return res.data[0]

    # ─────────────────────────────────────────────────────────
    # STUDENT: verify token and record attendance
    # ─────────────────────────────────────────────────────────
    def verify_and_attend(self, student_id: str, token: str) -> tuple[bool, str]:
        """
        Validates the QR token and records attendance atomically.
        Returns (success, message).
        """
        try:
            sb   = get_supabase_admin()
            now  = datetime.now(timezone.utc).isoformat()
            today = date.today().isoformat()

            # Fetch active, non-expired session
            sess_res = sb.table("qr_sessions") \
                         .select("*") \
                         .eq("token", token) \
                         .eq("is_active", True) \
                         .gt("expires_at", now) \
                         .execute()

            if not sess_res.data:
                return False, "❌ الـ QR منتهي الصلاحية أو غير صالح"

            sess = sess_res.data[0]

            # Check enrollment
            enr = sb.table("enrollments") \
                    .select("id") \
                    .eq("student_id", student_id) \
                    .eq("subject_id", sess["subject_id"]) \
                    .execute()
            if not enr.data:
                return False, "❌ أنت غير مسجل في هذه المادة"

            # Check already attended today
            existing = sb.table("attendance_records") \
                         .select("id, status") \
                         .eq("student_id", student_id) \
                         .eq("subject_id", sess["subject_id"]) \
                         .eq("date", today) \
                         .execute()
            if existing.data:
                status = existing.data[0].get("status", "present")
                label  = {"present": "حاضر", "late": "متأخر"}.get(status, status)
                return False, f"✅ تم تسجيل حضورك مسبقاً ({label})"

            # Determine status — late if > 10 min after session creation
            created_at = datetime.fromisoformat(
                sess["created_at"].replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()
            att_status = "late" if elapsed > 600 else "present"

            # Record attendance
            sb.table("attendance_records").insert({
                "student_id":  student_id,
                "subject_id":  sess["subject_id"],
                "lecture_id":  sess.get("lecture_id"),
                "date":        today,
                "status":      att_status,
                "check_in_at": datetime.now(timezone.utc).isoformat(),
                "method":      "qr",
                "recorded_by": student_id,
            }).execute()

            # Increment scan count
            sb.table("qr_sessions").update({
                "scan_count": sess["scan_count"] + 1
            }).eq("id", sess["id"]).execute()

            # Audit log
            sb.table("audit_logs").insert({
                "user_id":  student_id,
                "action":   "qr_attendance",
                "entity":   "attendance",
                "metadata": {
                    "subject_id": sess["subject_id"],
                    "session_id": sess["id"],
                    "status":     att_status,
                },
            }).execute()

            emoji = "✅" if att_status == "present" else "🕐"
            label = "حاضر" if att_status == "present" else "متأخر"
            return True, f"{emoji} تم تسجيل حضورك ({label})"

        except Exception as e:
            return False, f"خطأ: {e}"

    # ─────────────────────────────────────────────────────────
    # TEACHER: get live attendees for current session
    # ─────────────────────────────────────────────────────────
    def get_session_attendees(self, subject_id: str) -> list[dict]:
        """Returns today's QR-checked-in students for a subject."""
        try:
            sb    = get_supabase_admin()
            today = date.today().isoformat()
            res   = sb.table("attendance_records") \
                      .select("student_id, status, check_in_at, profiles(full_name)") \
                      .eq("subject_id", subject_id) \
                      .eq("date", today) \
                      .eq("method", "qr") \
                      .order("check_in_at") \
                      .execute()
            return res.data or []
        except Exception:
            return []

    def get_active_session(self, subject_id: str) -> dict | None:
        """Returns the currently active QR session for a subject, if any."""
        try:
            sb  = get_supabase_admin()
            now = datetime.now(timezone.utc).isoformat()
            res = sb.table("qr_sessions") \
                    .select("*") \
                    .eq("subject_id", subject_id) \
                    .eq("is_active", True) \
                    .gt("expires_at", now) \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .execute()
            return res.data[0] if res.data else None
        except Exception:
            return None

    def close_session(self, session_id: str) -> None:
        """Manually deactivates a QR session."""
        try:
            get_supabase_admin().table("qr_sessions") \
                .update({"is_active": False}) \
                .eq("id", session_id) \
                .execute()
        except Exception:
            pass

    def session_time_left(self, session: dict) -> int:
        """Returns seconds remaining for a session (0 if expired)."""
        try:
            expires = datetime.fromisoformat(
                session["expires_at"].replace("Z", "+00:00"))
            left = (expires - datetime.now(timezone.utc)).total_seconds()
            return max(0, int(left))
        except Exception:
            return 0
