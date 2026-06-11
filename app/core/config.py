import streamlit as st


def get_settings():
    """Read config from st.secrets (Streamlit Cloud) or environment variables."""
    try:
        # Streamlit Cloud / secrets.toml
        return {
            "supabase_url":              st.secrets["supabase"]["url"],
            "supabase_anon_key":         st.secrets["supabase"]["anon_key"],
            "supabase_service_role_key": st.secrets["supabase"]["service_role_key"],
        }
    except Exception:
        # Local .env fallback
        import os
        from dotenv import load_dotenv
        load_dotenv()
        return {
            "supabase_url":              os.getenv("SUPABASE_URL",""),
            "supabase_anon_key":         os.getenv("SUPABASE_ANON_KEY",""),
            "supabase_service_role_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY",""),
        }
