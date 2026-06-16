from __future__ import annotations
from datetime import datetime, date
from app.core.security import get_supabase, get_supabase_admin


class AttendanceService:

    def check_in(self, student_id: str, subject_id: str,
                 lecture_id: str = None, method: str = "manual",
                 recorded_by: str = None) -> tuple[bool, str]:
        try:
            sb = get_supabase_admin()
            today = date.today().isoformat()

            # Upsert attendance record
            sb.table("attendance_records").upsert({
                "student_id":  student_id,
                "subject_id":  subject_id,
                "lecture_id":  lecture_id,
                "date":        today,
                "status":      "present",
                "check_in_at": datetime.utcnow().isoformat(),
                "method":      method,
                "recorded_by": recorded_by,
            }, on_conflict="student_id,subject_id,date").execute()

            sb.table("audit_logs").insert({
                "user_id":  recorded_by or student_id,
                "action":   "attendance_checkin",
                "entity":   "attendance",
                "metadata": {"subject_id": subject_id, "method": method}
            }).execute()

            return True, "✅ تم تسجيل الحضور"
        except Exception as e:
            return False, f"خطأ: {e}"

    def get_subject_attendance(self, subject_id: str,
                               from_date: str = None,
                               to_date: str = None) -> list[dict]:
        try:
            sb = get_supabase_admin()
            q = sb.table("attendance_records")\
                  .select("*, profiles(full_name)")\
                  .eq("subject_id", subject_id)\
                  .order("date", desc=True)
            if from_date: q = q.gte("date", from_date)
            if to_date:   q = q.lte("date", to_date)
            return q.execute().data or []
        except Exception:
            return []

    def get_student_attendance(self, student_id: str,
                               subject_id: str = None) -> list[dict]:
        try:
            sb = get_supabase_admin()
            q = sb.table("attendance_records")\
                  .select("*, subjects(name_ar)")\
                  .eq("student_id", student_id)\
                  .order("date", desc=True)
            if subject_id:
                q = q.eq("subject_id", subject_id)
            return q.execute().data or []
        except Exception:
            return []

    def get_today_stats(self, subject_id: str) -> dict:
        try:
            sb = get_supabase_admin()
            today = date.today().isoformat()
            res = sb.table("attendance_records").select("status")\
                    .eq("subject_id", subject_id)\
                    .eq("date", today).execute()
            rows = res.data or []
            return {
                "present": sum(1 for r in rows if r["status"] == "present"),
                "absent":  sum(1 for r in rows if r["status"] == "absent"),
                "late":    sum(1 for r in rows if r["status"] == "late"),
                "total":   len(rows),
            }
        except Exception:
            return {"present": 0, "absent": 0, "late": 0, "total": 0}

    def update_status(self, student_id: str, subject_id: str,
                      record_date: str, status: str,
                      updated_by: str) -> None:
        sb = get_supabase_admin()
        sb.table("attendance_records").update({
            "status": status
        }).eq("student_id", student_id)\
          .eq("subject_id", subject_id)\
          .eq("date", record_date).execute()
        sb.table("audit_logs").insert({
            "user_id":  updated_by,
            "action":   "attendance_manual_edit",
            "entity":   "attendance",
            "metadata": {"student_id": student_id, "status": status, "date": record_date}
        }).execute()
