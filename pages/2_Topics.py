import streamlit as st
from psite_core import apply_base_theme, ensure_session_keys, get_topics, load_progress, save_progress

st.set_page_config(page_title="Topics — PSITE Mastery", layout="wide")
apply_base_theme()
ensure_session_keys()

st.markdown("<div class='psite-title'>Topics</div>", unsafe_allow_html=True)

topics = get_topics()
prog = load_progress()

top_row = st.columns([2,1,1])
with top_row[0]:
    q = st.text_input("Search topics", "", placeholder="filter…")
with top_row[1]:
    only_incomplete = st.toggle("Only incomplete", value=False)
with top_row[2]:
    if st.button("Mark all visible complete"):
        for t in topics:
            if q.lower() in t.lower() and (not prog[t].get("completed") if only_incomplete else True):
                prog[t]["completed"] = True
        save_progress(prog)

filtered = [t for t in topics if q.lower() in t.lower()]
if only_incomplete:
    filtered = [t for t in filtered if not prog[t].get("completed")]

st.markdown("<div class='grid-3'>", unsafe_allow_html=True)
cols = st.columns(3)
for i, topic in enumerate(filtered):
    with cols[i % 3]:
        with st.container(border=True):
            st.write(f"**{topic}**")
            acc = 0.0
            if prog[topic]["total"] > 0:
                acc = prog[topic]["correct"] / prog[topic]["total"]
            st.caption(f"Accuracy: {int(acc*100)}% • Attempts: {prog[topic]['total']}")
            # Completed toggle
            new_done = st.checkbox("Completed", value=prog[topic]["completed"], key=f"done_{i}")
            if new_done != prog[topic]["completed"]:
                prog[topic]["completed"] = new_done
                save_progress(prog)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Review", key=f"rev_{i}"):
                    st.session_state.active_topic = topic
                    st.switch_page("pages/3_Review.py")
            with c2:
                if st.button("Start Quiz", key=f"quiz_{i}"):
                    st.session_state.active_topic = topic
                    st.switch_page("pages/4_Quiz.py")
st.markdown("</div>", unsafe_allow_html=True)
