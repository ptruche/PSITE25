import streamlit as st
from psite_core import apply_base_theme, ensure_session_keys, load_progress, suggested_topics

st.set_page_config(page_title="Dashboard — PSITE Mastery", layout="wide")
apply_base_theme()
ensure_session_keys()

st.markdown("<div class='psite-title'>Dashboard</div>", unsafe_allow_html=True)
prog = load_progress()

tot_correct, tot_total = 0, 0
for rec in prog.values():
    tot_correct += rec.get("correct", 0)
    tot_total += rec.get("total", 0)
overall = (tot_correct / tot_total) if tot_total else 0.0

c1, c2, c3 = st.columns([2,2,2])
with c1:
    st.metric("Overall Mastery", f"{int(overall*100)}%")
    st.progress(overall)
with c2:
    mastered = sum(1 for r in prog.values() if r.get("mastered"))
    st.metric("Mastered Topics", f"{mastered}")
with c3:
    attempted = sum(1 for r in prog.values() if r.get("total",0)>0)
    st.metric("Attempted Topics", f"{attempted}")

st.markdown("### Suggested Next Topics")
suggest = suggested_topics(6)
cols = st.columns(3)
for i, (t, acc) in enumerate(suggest):
    with cols[i % 3]:
        with st.container(border=True):
            st.write(f"**{t}**")
            st.caption(f"Accuracy: {int(acc*100)}%")
            go = st.button("Review", key=f"dbr_{i}")
            if go:
                st.session_state.active_topic = t
                st.switch_page("pages/3_Review.py")

st.markdown("### Resume")
colA, colB = st.columns(2)
with colA:
    if st.button("Resume Quiz"):
        st.switch_page("pages/4_Quiz.py")
with colB:
    if st.button("Open Topics"):
        st.switch_page("pages/2_Topics.py")
