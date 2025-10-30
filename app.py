# app.py
import streamlit as st
import pandas as pd

from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, get_topics, resolve_review_path,
    load_questions_for_subjects, load_questions_frame,
    questions_count_by_topic, record_attempt, overall_accuracy,
    accuracy_timeseries, topic_strengths, sr_due_ids, sr_update,
    load_progress,  # explicit import (used by analytics)
    # debug helpers
    debug_scan_report, question_roots
)

st.set_page_config(page_title="PSITE Mastery", page_icon=None, layout="wide", initial_sidebar_state="expanded")
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# ---------------- Header ----------------
st.markdown("""
<div class="app-header">
  <div class="app-header-inner">
    <div class="app-brand"><div class="app-title">PSITE Mastery</div></div>
    <div id="logout-slot"></div>
  </div>
</div>
""", unsafe_allow_html=True)

# Logout in header
rc = st.columns([1,8,1])[0]
with rc:
    if auth_is_authed():
        auth_logout_button()

# ---------------- Login gate ----------------
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, analytics, and quizzes.")
    auth_login_form()
    st.stop()

# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### Navigate")
    if st.button("Dashboard", use_container_width=True):
        st.session_state.view = "dashboard"; st.rerun()
    if st.button("All Topics", use_container_width=True):
        st.session_state.view = "topics"; st.rerun()
    if st.button("Make Quiz", use_container_width=True):
        st.session_state.view = "make_quiz"; st.rerun()
    if st.button("Spaced Repetition ▶", use_container_width=True):
        ids = sr_due_ids(limit=50)
        df_all = load_questions_frame()
        pool = df_all[df_all["id"].isin(ids)].reset_index(drop=True) if not df_all.empty else df_all
        st.session_state.quiz_pool = pool
        st.session_state.quiz_idx = 0
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.session_state.quiz_finished = False
        st.session_state.quiz_mode = "spaced"
        st.session_state.view = "quiz"
        st.rerun()
    if st.button("Analytics", use_container_width=True):
        st.session_state.view = "analytics"; st.rerun()

    st.markdown("---")
    # Optional debug drawer—helps verify discovery and parsing
    with st.expander("Debug questions", expanded=False):
        st.caption("Roots scanned:")
        for r in question_roots():
            st.code(r)
        df_dbg = debug_scan_report()
        if df_dbg.empty:
            st.caption("No .md files discovered in roots above.")
        else:
            st.dataframe(df_dbg, use_container_width=True, hide_index=True)

    st.markdown("---")
    auth_logout_button()

# ---------------- Utilities ----------------
def _render_topic_card(topic: str, q_total_map: dict, progress_map: dict):
    total_q = q_total_map.get(topic, 0)
    attempted = progress_map.get(topic, {}).get("total", 0)
    pct_done = int(100 * attempted / total_q) if total_q else 0
    st.markdown(f"""
    <div class="topic-card">
      <div class="topic-title">{topic}</div>
      <div class="topic-row">
        <div class="meter"><span style="width:{pct_done}%"></span></div>
        <div style="width:42px;text-align:right;font-size:.85rem;">{pct_done}%</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Review", key=f"rev_{topic}", use_container_width=True):
            st.session_state.active_topic = topic
            st.session_state.view = "review"
            st.rerun()
    with c2:
        if st.button("Make Quiz", key=f"quiz_{topic}", use_container_width=True):
            df = load_questions_for_subjects([topic])
            st.session_state.active_topic = topic
            st.session_state.quiz_pool = df.reset_index(drop=True)
            st.session_state.quiz_idx = 0
            st.session_state.quiz_answers = {}
            st.session_state.quiz_revealed = set()
            st.session_state.quiz_finished = False
            st.session_state.quiz_mode = "normal"
            st.session_state.view = "quiz"
            st.rerun()

# ---------------- Views ----------------
def view_dashboard():
    st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
    acc = overall_accuracy()
    st.metric("Overall Correct", f"{int(round(acc*100))}%")

    series = accuracy_timeseries(days=30)
    if series:
        dates = [d for d,_,_ in series]
        accs  = [a for _,a,_ in series]
        counts= [n for _,_,n in series]
        import matplotlib.pyplot as plt
        fig1 = plt.figure()
        plt.plot(dates, [a*100 for a in accs])
        plt.xticks(rotation=45, ha="right")
        plt.ylabel("% Correct")
        plt.title("Last 30 days")
        st.pyplot(fig1, clear_figure=True)
        fig2 = plt.figure()
        plt.bar(dates, counts)
        plt.xticks
