import streamlit as st
from psite_core import apply_base_theme

st.set_page_config(page_title="PSITE Mastery", page_icon=None, layout="wide")
apply_base_theme()

st.markdown(
    """
    <div style="display:flex;align-items:center;gap:.6rem;margin:.2rem 0 0.8rem 0;">
      <div style="font-weight:800;font-size:1.2rem;">PSITE Mastery</div>
      <div style="opacity:.7;">Practice • Review • Analytics</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info("Use the left sidebar to open **Dashboard**, **Topics**, **Review**, **Quiz**, or **Analytics**.")
