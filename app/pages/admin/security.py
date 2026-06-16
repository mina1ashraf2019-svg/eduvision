import streamlit as st
from app.core.security import get_supabase_admin, get_current_user_id
from app.services.device_service import DeviceService
from translations import get_lang


def show_security():
    lang = get_lang()
    uid  = get_current_user_id()
    sb   = get_supabase_admin()
    svc  = DeviceService()

    st.title("🔒 " + ("الأمان والأجهزة" if lang=="ar" else "Security & Devices"))

    tab1, tab2, tab3 = st.tabs([
        "📱 الأجهزة",
        "⚠️ التنبيهات الأمنية",
        "🖥️ الجلسات النشطة"
    ])

    # ── DEVICES TAB ───────────────────────────────────────────
    with tab1:
        st.subheader("📱 كل الأجهزة المسجلة")

        # System config
        with st.expander("⚙️ إعدادات الأجهزة"):
            try:
                config_res = sb.table("system_config").select("*").execute()
                configs = {c["key"]: c["value"] for c in (config_res.data or [])}
            except Exception:
                configs = {}

            c1, c2, c3 = st.columns(3)
            with c1:
                max_dev = st.number_input("الحد الأقصى للأجهزة",
                                          1, 10,
                                          int(configs.get("max_devices_per_student","2")))
            with c2:
                action  = st.selectbox("عند تجاوز الحد",
                                       ["block","warn"],
                                       index=0 if configs.get("device_limit_action","block")=="block" else 1)
            with c3:
                watermark = st.checkbox("تفعيل الـ Watermark",
                                        value=configs.get("watermark_enabled","true")=="true")

            if st.button("💾 حفظ الإعدادات"):
                for k, v in [("max_devices_per_student", str(max_dev)),
                              ("device_limit_action", action),
                              ("watermark_enabled", str(watermark).lower())]:
                    sb.table("system_config").upsert({"key": k, "value": v,
                                                       "updated_by": uid}).execute()
                st.success("✅ تم حفظ الإعدادات")
                st.rerun()

        devices = svc.get_all_devices()
        if not devices:
            st.info("لا توجد أجهزة مسجلة بعد.")
        else:
            for d in devices:
                student_name = (d.get("profiles") or {}).get("full_name", "—")
                blocked = d.get("is_blocked", False)
                status_icon = "🔴" if blocked else "🟢"

                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1, 1])
                c1.markdown(f"**{student_name}**")
                c2.markdown(f"{d.get('platform','—')} / {d.get('browser','—')}")
                c3.markdown(f"آخر ظهور: {str(d.get('last_seen',''))[:10]}")
                c4.markdown(f"{status_icon} {'محظور' if blocked else 'نشط'}")

                if not blocked:
                    if c5.button("🚫 حظر", key=f"blk_{d['id']}"):
                        svc.block_device(d["id"], uid)
                        st.rerun()
                else:
                    if c5.button("✅ رفع الحظر", key=f"unblk_{d['id']}"):
                        sb.table("student_devices").update({"is_blocked": False})\
                          .eq("id", d["id"]).execute()
                        st.rerun()
                st.divider()

    # ── ALERTS TAB ────────────────────────────────────────────
    with tab2:
        st.subheader("⚠️ التنبيهات الأمنية")

        try:
            alerts_res = sb.table("security_alerts")\
                           .select("*, profiles(full_name)")\
                           .eq("resolved", False)\
                           .order("created_at", desc=True).execute()
            alerts = alerts_res.data or []
        except Exception as e:
            st.error(f"خطأ: {e}")
            alerts = []

        if not alerts:
            st.success("✅ لا توجد تنبيهات غير محلولة")
        else:
            st.warning(f"⚠️ {len(alerts)} تنبيه يحتاج مراجعة")
            for a in alerts:
                student_name = (a.get("profiles") or {}).get("full_name","—")
                severity_color = {"critical":"🔴","high":"🟠","medium":"🟡","low":"🟢"}\
                                  .get(a["severity"],"🟡")
                with st.expander(
                    f"{severity_color} {a['alert_type']} — {student_name} — {str(a['created_at'])[:10]}"
                ):
                    st.json(a.get("details", {}))
                    c1, c2 = st.columns(2)
                    if c1.button("✅ حل التنبيه", key=f"res_{a['id']}"):
                        sb.table("security_alerts").update({
                            "resolved":    True,
                            "resolved_by": uid,
                            "resolved_at": __import__("datetime").datetime.utcnow().isoformat(),
                        }).eq("id", a["id"]).execute()
                        st.rerun()
                    if c2.button("🧊 تجميد الحساب", key=f"frz_{a['id']}"):
                        sb.table("profiles").update({"account_status":"frozen"})\
                          .eq("id", a["student_id"]).execute()
                        sb.table("audit_logs").insert({
                            "user_id":  uid,
                            "action":   "account_frozen",
                            "entity":   "profile",
                            "entity_id": a["student_id"],
                        }).execute()
                        st.success("تم تجميد الحساب")
                        st.rerun()

    # ── SESSIONS TAB ──────────────────────────────────────────
    with tab3:
        st.subheader("🖥️ الجلسات النشطة")
        try:
            sess_res = sb.table("active_sessions")\
                         .select("*, profiles(full_name)")\
                         .eq("is_active", True)\
                         .order("started_at", desc=True).execute()
            sessions = sess_res.data or []
        except Exception:
            sessions = []

        if not sessions:
            st.info("لا توجد جلسات نشطة حالياً")
        else:
            st.info(f"🖥️ {len(sessions)} جلسة نشطة")
            for s in sessions:
                name = (s.get("profiles") or {}).get("full_name","—")
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                c1.markdown(f"**{name}**")
                c2.markdown(f"IP: {s.get('ip_address','—')}")
                c3.markdown(f"بدأت: {str(s.get('started_at',''))[:16]}")
                if c4.button("🚫 إنهاء", key=f"term_{s['id']}"):
                    sb.table("active_sessions").update({
                        "is_active":          False,
                        "terminated_by":      uid,
                        "terminated_at":      __import__("datetime").datetime.utcnow().isoformat(),
                        "termination_reason": "admin_action",
                    }).eq("id", s["id"]).execute()
                    st.rerun()
