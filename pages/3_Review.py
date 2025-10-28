import streamlit as st
from psite_core import (
    apply_base_theme, ensure_session_keys, resolve_review_path,
    load_progress, save_progress
)

st.set_page_config(page_title="Review — PSITE Mastery", layout="wide")
apply_base_theme()
ensure_session_keys()

prog = load_progress()
topic = st.session_state.get("active_topic")

hdr = st.columns([1,5,2])
with hdr[0]:
    if st.button("← All Topics", type="secondary"):
        st.switch_page("pages/2_Topics.py")
with hdr[1]:
    st.markdown("<div class='psite-title'>Review</div>", unsafe_allow_html=True)
with hdr[2]:
    if topic:
        done = st.toggle("Mark Completed", value=prog[topic]["completed"])
        if done != prog[topic]["completed"]:
            prog[topic]["completed"] = done
            save_progress(prog)

if not topic:
    st.info("Pick a topic from **Topics**.")
    st.stop()

st.subheader(topic)
path = resolve_review_path(topic)
if not path:
    st.info("No review uploaded yet. Add a markdown file into `data/reviews/` named like the topic (slug).")
else:
    with open(path, "r", encoding="utf-8") as f:
        st.markdown(f.read(), unsafe_allow_html=True)

st.divider()
if st.button("Test me on this topic"):
    st.switch_page("pages/4_Quiz.py")
