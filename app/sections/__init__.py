"""
Section Dispatcher — EduVision v3
Renderer path loaded from section_types.renderer in DB.
Adding a new section type = create renderer file + INSERT DB row only.
"""
from __future__ import annotations
import importlib, json
import streamlit as st
from typing import Optional


@st.cache_data(ttl=300)
def _get_renderer_path(section_type: str) -> Optional[str]:
    try:
        from app.core.security import get_supabase
        sb = get_supabase()
        res = sb.table("section_types")\
                .select("renderer")\
                .eq("type_key", section_type)\
                .eq("is_active", True)\
                .single().execute()
        return res.data["renderer"] if res.data else None
    except Exception:
        return None


def render_section(section: dict, student_id: str, lang: str) -> None:
    if not section.get("is_enabled", True):
        return
    section_type  = section["section_type"]
    renderer_path = _get_renderer_path(section_type)
    if not renderer_path:
        st.warning(f"⚠️ نوع القسم غير مسجل: `{section_type}`")
        return
    try:
        config = json.loads(section.get("config_json") or "{}")
    except json.JSONDecodeError:
        config = {}
    try:
        module_path, func_name = renderer_path.rsplit(".", 1)
        module   = importlib.import_module(module_path)
        renderer = getattr(module, func_name)
        renderer(config=config, student_id=student_id,
                 lang=lang, section_id=section["id"])
    except (ImportError, AttributeError) as e:
        st.error(f"❌ خطأ في تحميل القسم `{section_type}`: {e}")
    except Exception as e:
        st.error(f"❌ خطأ في عرض القسم: {e}")
