from __future__ import annotations
from datetime import datetime
import streamlit as st
from app.core.security import get_supabase

# Section types that DON'T block lecture completion
OPTIONAL_SECTIONS = {"discussion", "attachments", "links"}


class ProgressService:

    def mark_section_complete(self, student_id: str, section_id: str) -> None:
        """Mark one section as complete, then recompute lecture progress."""
        try:
            sb = get_supabase()
            sb.table("student_section_progress").upsert({
                "student_id":   student_id,
                "section_id":   section_id,
                "completed":    True,
                "completed_at": datetime.utcnow().isoformat(),
            }, on_conflict="student_id,section_id").execute()

            self._recompute_lecture_progress(student_id, section_id)
        except Exception as e:
            # Non-fatal — don't break the student's experience
            pass

    def _recompute_lecture_progress(self, student_id: str, section_id: str) -> None:
        try:
            sb = get_supabase()

            # Get lecture_id from section
            sec_res = sb.table("lecture_sections")\
                        .select("lecture_id")\
                        .eq("id", section_id).single().execute()
            if not sec_res.data:
                return
            lecture_id = sec_res.data["lecture_id"]

            # Get lecture's subject_id
            lec_res = sb.table("lectures")\
                        .select("subject_id")\
                        .eq("id", lecture_id).single().execute()
            if not lec_res.data:
                return
            subject_id = lec_res.data["subject_id"]

            # All enabled sections for this lecture
            sections_res = sb.table("lecture_sections")\
                             .select("id, section_type")\
                             .eq("lecture_id", lecture_id)\
                             .eq("is_enabled", True).execute()
            all_sections = sections_res.data or []

            # Required sections (exclude optional types)
            required = [s for s in all_sections
                        if s["section_type"] not in OPTIONAL_SECTIONS]

            if not required:
                pct = 100
            else:
                required_ids = [s["id"] for s in required]
                done_res = sb.table("student_section_progress")\
                             .select("section_id")\
                             .eq("student_id", student_id)\
                             .eq("completed", True)\
                             .in_("section_id", required_ids).execute()
                completed_count = len(done_res.data or [])
                pct = int(completed_count / len(required) * 100)

            is_completed = pct >= 100

            sb.table("student_progress").upsert({
                "student_id":   student_id,
                "lecture_id":   lecture_id,
                "subject_id":   subject_id,
                "progress_pct": pct,
                "is_completed": is_completed,
                "last_viewed":  datetime.utcnow().isoformat(),
            }, on_conflict="student_id,lecture_id").execute()

        except Exception:
            pass

    def get_lecture_progress(self, student_id: str, lecture_id: str) -> dict:
        try:
            sb = get_supabase()
            res = sb.table("student_progress")\
                    .select("*")\
                    .eq("student_id", student_id)\
                    .eq("lecture_id", lecture_id)\
                    .single().execute()
            return res.data or {"progress_pct": 0, "is_completed": False}
        except Exception:
            return {"progress_pct": 0, "is_completed": False}

    def get_subject_progress(self, student_id: str, subject_id: str) -> int:
        try:
            sb = get_supabase()
            res = sb.table("student_progress")\
                    .select("progress_pct")\
                    .eq("student_id", student_id)\
                    .eq("subject_id", subject_id).execute()
            rows = res.data or []
            if not rows:
                return 0
            return int(sum(r["progress_pct"] for r in rows) / len(rows))
        except Exception:
            return 0

    def get_all_progress_for_subject(self, student_id: str, subject_id: str) -> dict:
        """Returns {lecture_id: {progress_pct, is_completed, last_viewed}}"""
        try:
            sb = get_supabase()
            res = sb.table("student_progress")\
                    .select("lecture_id, progress_pct, is_completed, last_viewed")\
                    .eq("student_id", student_id)\
                    .eq("subject_id", subject_id).execute()
            return {r["lecture_id"]: r for r in (res.data or [])}
        except Exception:
            return {}

    def get_completed_sections(self, student_id: str, section_ids: list[str]) -> set[str]:
        try:
            sb = get_supabase()
            res = sb.table("student_section_progress")\
                    .select("section_id")\
                    .eq("student_id", student_id)\
                    .eq("completed", True)\
                    .in_("section_id", section_ids).execute()
            return {r["section_id"] for r in (res.data or [])}
        except Exception:
            return set()
