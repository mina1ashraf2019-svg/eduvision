import streamlit as st
from app.services.progress_service import ProgressService


def render_hw_upload(config: dict, student_id: str, lang: str, section_id: str):
    st.info(f"🚧 قسم '{sec_type}' — سيتم تفعيله قريباً")
    ProgressService().mark_section_complete(student_id, section_id)
