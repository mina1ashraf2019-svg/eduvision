from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from app.core.security import get_supabase, get_supabase_admin


class DeviceService:

    # ─────────────────────────────────────────────────────────
    # SERVER-SIDE FINGERPRINTING  (SEC-01)
    # Client can no longer send a fake fingerprint
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def compute_fingerprint(student_id: str, ip: str, user_agent: str) -> str:
        raw = f"{student_id}:{ip.split(',')[0].strip()}:{user_agent}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _get_config(self, key: str, default: str = "2") -> str:
        try:
            res = get_supabase().table("system_config") \
                                .select("value").eq("key", key).single().execute()
            return res.data["value"] if res.data else default
        except Exception:
            return default

    # ─────────────────────────────────────────────────────────
    # REGISTER DEVICE
    # ─────────────────────────────────────────────────────────
    def register_device(self, student_id: str,
                        ip: str = "", user_agent: str = "",
                        device_name: str = "", platform: str = "",
                        browser: str = "") -> tuple[bool, str]:
        """
        Computes fingerprint server-side from IP + User-Agent.
        Returns (allowed, message).
        """
        sb          = get_supabase_admin()
        max_devices = int(self._get_config("max_devices_per_student", "2"))
        fingerprint = self.compute_fingerprint(student_id, ip, user_agent)

        # Already known device?
        existing = sb.table("student_devices") \
                     .select("id, is_blocked") \
                     .eq("student_id", student_id) \
                     .eq("fingerprint", fingerprint) \
                     .execute().data or []

        if existing:
            if existing[0].get("is_blocked"):
                return False, "هذا الجهاز محظور. تواصل مع المشرف."
            # Update last_seen
            sb.table("student_devices") \
              .update({"last_seen": datetime.now(timezone.utc).isoformat()}) \
              .eq("id", existing[0]["id"]).execute()
            return True, "جهاز معروف"

        # New device — check limit
        all_devices = sb.table("student_devices") \
                        .select("id", count="exact") \
                        .eq("student_id", student_id) \
                        .eq("is_blocked", False) \
                        .execute()
        count = all_devices.count or 0

        action = self._get_config("device_limit_action", "block")
        if count >= max_devices:
            if action == "block":
                # Log security alert
                try:
                    sb.table("security_alerts").insert({
                        "student_id": student_id,
                        "alert_type": "device_limit_exceeded",
                        "severity":   "medium",
                        "details":    {"fingerprint": fingerprint, "ip": ip},
                    }).execute()
                except Exception:
                    pass
                return False, f"وصلت لحد الأجهزة المسموح بها ({max_devices}). تواصل مع المشرف."
            else:
                # warn mode — allow but alert
                try:
                    sb.table("security_alerts").insert({
                        "student_id": student_id,
                        "alert_type": "device_limit_warning",
                        "severity":   "low",
                        "details":    {"fingerprint": fingerprint, "ip": ip},
                    }).execute()
                except Exception:
                    pass

        # Register new device
        device_name_safe = device_name or _ua_summary(user_agent)
        sb.table("student_devices").insert({
            "student_id":  student_id,
            "fingerprint": fingerprint,
            "device_name": device_name_safe[:100],
            "platform":    platform[:50] if platform else _platform_from_ua(user_agent),
            "browser":     browser[:50]  if browser  else _browser_from_ua(user_agent),
            "ip_address":  ip.split(",")[0].strip()[:45],
            "last_seen":   datetime.now(timezone.utc).isoformat(),
        }).execute()

        return True, "تم تسجيل جهازك بنجاح"

    # ─────────────────────────────────────────────────────────
    # ADMIN HELPERS
    # ─────────────────────────────────────────────────────────
    def get_all_devices(self) -> list[dict]:
        try:
            return get_supabase_admin() \
                .table("student_devices") \
                .select("*, profiles(full_name)") \
                .order("last_seen", desc=True) \
                .execute().data or []
        except Exception:
            return []

    def get_student_devices(self, student_id: str) -> list[dict]:
        try:
            return get_supabase_admin() \
                .table("student_devices") \
                .select("*") \
                .eq("student_id", student_id) \
                .order("last_seen", desc=True) \
                .execute().data or []
        except Exception:
            return []

    def block_device(self, device_id: str, blocked_by: str) -> bool:
        try:
            get_supabase_admin() \
                .table("student_devices") \
                .update({"is_blocked": True, "blocked_by": blocked_by}) \
                .eq("id", device_id).execute()
            return True
        except Exception:
            return False

    def revoke_all_devices(self, student_id: str) -> int:
        try:
            res = get_supabase_admin() \
                .table("student_devices") \
                .delete() \
                .eq("student_id", student_id) \
                .execute()
            return len(res.data or [])
        except Exception:
            return 0


# ─────────────────────────────────────────────────────────
# UA HELPERS  (lightweight — no extra dependency)
# ─────────────────────────────────────────────────────────
def _ua_summary(ua: str) -> str:
    ua = ua or ""
    if "iPhone" in ua or "iPad" in ua:
        return "iOS Device"
    if "Android" in ua:
        return "Android Device"
    if "Windows" in ua:
        return "Windows PC"
    if "Mac" in ua:
        return "Mac"
    if "Linux" in ua:
        return "Linux"
    return "Unknown Device"


def _platform_from_ua(ua: str) -> str:
    ua = ua or ""
    for kw, label in [("iPhone","iOS"),("iPad","iOS"),("Android","Android"),
                      ("Windows","Windows"),("Mac","macOS"),("Linux","Linux")]:
        if kw in ua:
            return label
    return "Unknown"


def _browser_from_ua(ua: str) -> str:
    ua = ua or ""
    for kw, label in [("Edg/","Edge"),("Chrome","Chrome"),
                      ("Firefox","Firefox"),("Safari","Safari"),("OPR","Opera")]:
        if kw in ua:
            return label
    return "Unknown"
