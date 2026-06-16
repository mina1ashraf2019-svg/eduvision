from __future__ import annotations
import hashlib
from datetime import datetime
from app.core.security import get_supabase, get_supabase_admin
from app.core.exceptions import EduVisionError


class DeviceService:

    def _get_config(self, key: str, default: str = "2") -> str:
        try:
            res = get_supabase().table("system_config")\
                                .select("value").eq("key", key).single().execute()
            return res.data["value"] if res.data else default
        except Exception:
            return default

    def register_device(self, student_id: str, fingerprint: str,
                        device_name: str = "", platform: str = "",
                        browser: str = "", ip: str = "") -> tuple[bool, str]:
        """
        Register device for student.
        Returns (allowed, message).
        """
        sb = get_supabase_admin()
        max_devices = int(self._get_config("max_devices_per_student", "2"))

        # Check if device already registered
        existing = sb.table("student_devices")\
                     .select("id, is_blocked")\
                     .eq("student_id", student_id)\
                     .eq("device_fingerprint", fingerprint).execute()

        if existing.data:
            device = existing.data[0]
            if device["is_blocked"]:
                return False, "هذا الجهاز محظور. تواصل مع المشرف."
            # Update last_seen
            sb.table("student_devices").update({"last_seen": datetime.utcnow().isoformat()})\
              .eq("id", device["id"]).execute()
            return True, "جهاز معروف"

        # Check device limit
        count_res = sb.table("student_devices")\
                      .select("id", count="exact")\
                      .eq("student_id", student_id)\
                      .eq("is_blocked", False).execute()
        count = count_res.count or 0

        if count >= max_devices:
            action = self._get_config("device_limit_action", "block")
            # Create security alert
            sb.table("security_alerts").insert({
                "student_id": student_id,
                "alert_type": "device_limit_exceeded",
                "severity":   "high",
                "details":    {"device_count": count, "max": max_devices,
                               "new_fingerprint": fingerprint, "platform": platform},
            }).execute()
            if action == "block":
                return False, f"وصلت للحد الأقصى ({max_devices} أجهزة). تواصل مع المشرف."
            else:
                return True, "تحذير: وصلت للحد الأقصى للأجهزة"

        # Register new device
        sb.table("student_devices").insert({
            "student_id":         student_id,
            "device_fingerprint": fingerprint,
            "device_name":        device_name or f"{platform} - {browser}",
            "platform":           platform,
            "browser":            browser,
            "ip_address":         ip,
        }).execute()

        sb.table("audit_logs").insert({
            "user_id":  student_id,
            "action":   "device_registered",
            "entity":   "device",
            "metadata": {"platform": platform, "browser": browser}
        }).execute()

        return True, "تم تسجيل الجهاز بنجاح"

    def get_student_devices(self, student_id: str) -> list[dict]:
        try:
            sb = get_supabase_admin()
            res = sb.table("student_devices").select("*")\
                    .eq("student_id", student_id)\
                    .order("last_seen", desc=True).execute()
            return res.data or []
        except Exception:
            return []

    def block_device(self, device_id: str, blocked_by: str) -> None:
        sb = get_supabase_admin()
        sb.table("student_devices").update({
            "is_blocked": True,
            "blocked_by": blocked_by,
            "blocked_at": datetime.utcnow().isoformat(),
        }).eq("id", device_id).execute()
        sb.table("audit_logs").insert({
            "user_id":  blocked_by,
            "action":   "device_blocked",
            "entity":   "device",
            "entity_id": device_id,
        }).execute()

    def remove_device(self, device_id: str, removed_by: str) -> None:
        sb = get_supabase_admin()
        sb.table("student_devices").delete().eq("id", device_id).execute()
        sb.table("audit_logs").insert({
            "user_id":  removed_by,
            "action":   "device_removed",
            "entity":   "device",
            "entity_id": device_id,
        }).execute()

    def get_all_devices(self, limit: int = 200) -> list[dict]:
        try:
            sb = get_supabase_admin()
            res = sb.table("student_devices")\
                    .select("*, profiles(full_name)")\
                    .order("last_seen", desc=True).limit(limit).execute()
            return res.data or []
        except Exception:
            return []
