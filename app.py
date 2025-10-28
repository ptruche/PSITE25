# app.py
import streamlit as st
import pandas as pd

from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, resolve_review_path, load_questions_for_subjects,
    load_questions_frame, update_topic_stats, sr_due_ids, sr_update,
    overall_accuracy, accuracy_history_series, get_strengths_weaknesses,
    all_topics_progress, topic_completion
)

# ---------- Base layout ----------
st.set_page_config(page_title="PSITE Mastery", page_icon=None, layout="wide", initial_sidebar_state="expanded")
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# Header
st.markdown("""
<div class="app-header">
  <div class="app-header-inner">
    <div class="app-title">PSITE Mastery</div>
    <div id="logout-slot"></div>
  </div>
</div>
""", unsafe_allow_html=True)

# Logout in header area
hdr_left, hdr_mid, hdr_right = st.columns([1,8,1])
with hdr_left:
    if auth_is_authed():
        auth_logout_button()

# Auth gate
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, reviews, and quizzes.")
    auth_login_form()
    st.stop()

# ---------- Sidebar (your requested options) ----------
with st.sidebar:
    st.markdown("### Navigate")
    if st.button("Dashboard", use_container_width=True):
        st.session_state.view = "dashboard"; st.rerun()
    if st.button("Make Quiz", use_container_width=True):
        st.session_state.view = "make_quiz"; st.rerun()
    if st.button("Spaced Rep ▶", use_container_width=True):
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
    if st.button("All Topics", use_container_width=True):
        st.session_state.view = "topics"; st.rerun()
    if st.button("Analytics", use_container_width=True):
        st.session_state.view = "analytics"; st.rerun()
    st.markdown("---")
    # Keep a small logout here too
    auth_logout_button()

# ---------- Helpers ----------
def _topics_flat():
    cats = get_category_map()
    return [(cat, t) for cat, arr in cats.items() for t in arr]

def _topic_list():
    return [t for _, t in _topics_flat()]

def _render_topics_grid_with_progress(filtered_topics):
    """Grid with Review / Make Quiz buttons + completion tracker."""
    if not filtered_topics:
        st.info("No topics match your filter.")
        return
    counts_df = all_topics_progress().set_index("topic")
    cols_per_row = 3
    rows = (len(filtered_topics) + cols_per_row - 1) // cols_per_row
    idx = 0
    for _ in range(rows):
        cols = st.columns(cols_per_row)
        for c in cols:
            if idx >= len(filtered_topics): break
            topic = filtered_topics[idx]
            # Completion %
            comp = 0.0
            if topic in counts_df.index and counts_df.loc[topic]["completion"] == counts_df.loc[topic]["completion"]:
                comp = float(counts_df.loc[topic]["completion"])
            pct = int(round(comp * 100))
            with c:
                st.markdown(f"""
                <div class="topic-card">
                  <div class="topic-title">{topic}</div>
                  <div class="progress-wrap"><div class="progress-fill" style="width:{pct}%"></div></div>
                  <div style="font-size:.8rem; color:#6b7280;">{pct}% of this topic attempted</div>
                  <div class="topic-actions">
                    <button class="tiny-btn" onclick="window.parent.postMessage({{'topicSelect': {repr(topic)}}}, '*')">Review</button>
                    <button class="tiny-btn secondary" onclick="window.parent.postMessage({{'topicQuiz': {repr(topic)}}}, '*')">Make Quiz</button>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            idx += 1

    # Bridge Review / Make Quiz buttons to Streamlit
    st.markdown("""
    <script>
      window.addEventListener('message', (e) => {
        const data = e.data || {};
        if (data.topicSelect) {
          window.parent.postMessage({streamlitSetComponentValue: {key:'__topic_select__', value:data.topicSelect}}, '*');
        }
        if (data.topicQuiz) {
          window.parent.postMessage({streamlitSetComponentValue: {key:'__topic_quiz__', value:data.topicQuiz}}, '*');
        }
      });
    </script>
    """, unsafe_allow_html=True)

    sel = st.session_state.get("__topic_select__")
    if sel:
        st.session_state.active_topic = sel
        st.session_state.view = "review"
        st.session_state["__topic_select__"] = None
        st.rerun()
    qsel = st.session_state.get("__topic_quiz__")
    if qsel:
        df = load_questions_for_subjects([qsel])
        st.session_state.quiz_pool = df.reset_index(drop=True)
        st.session_state.quiz_idx = 0
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.session_state.quiz_finished = False
        st.session_state.quiz_mode = "normal"
        st.session_state.view = "quiz"
        st.session_state["__topic_quiz__"] = None
        st.rerun()

# ---------- Views ----------
def render_dashboard():
    st.markdown("<div class='section-title'>Dashboard</div>", unsafe_allow_html=True)

    # Top KPIs
    acc = overall_accuracy()
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric("Overall Correct", f"{int(round(acc*100))}%")
    # Strong/weak summaries
    strongest, weakest = get_strengths_weaknesses(k=3, min_attempts=3)
    with kpi2:
        if strongest:
            st.write("**Strongest topics**")
            for t, a, n in strongest:
                st.caption(f"{t} — {int(round(a*100))}% ({n} q)")
        else:
            st.caption("_Answer a few questions to see strengths._")
    with kpi3:
        if weakest:
            st.write("**Weakest topics**")
            for t, a, n in weakest:
                st.caption(f"{t} — {int(round(a*100))}% ({n} q)")
        else:
            st.caption("_Answer a few questions to see weaknesses._")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # Trend line
    st.markdown("**Accuracy over time**")
    series = accuracy_history_series()
    if series.empty:
        st.caption("_Your trend will appear once you start quizzing._")
    else:
        series = series.copy()
        series["date"] = pd.to_datetime(series["ts"], unit="s")
        series = series.groupby("date", as_index=False)["overall_acc"].last()
        # Streamlit simple line chart
        st.line_chart(series.set_index("date"))

def render_make_quiz():
    st.markdown("<div class='section-title'>Make a Quiz</div>", unsafe_allow_html=True)
    topics = ["Any topic"] + _topic_list()
    topic_pick = st.selectbox("Topic", topics, index=0)
    n = st.slider("Number of questions", 5, 50, 20, step=5)
    start = st.button("Start ▶", use_container_width=True)
    if start:
        if topic_pick == "Any topic":
            df = load_questions_frame()
        else:
            df = load_questions_for_subjects([topic_pick])
            st.session_state.active_topic = topic_pick
        st.session_state.quiz_pool = df.sample(n=min(len(df), int(n)), random_state=42).reset_index(drop=True) if not df.empty else df
        st.session_state.quiz_idx = 0
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.session_state.quiz_finished = False
        st.session_state.quiz_mode = "normal"
        st.session_state.view = "quiz"
        st.rerun()

def render_topics():
    st.markdown("<div class='section-title'>All Topics</div>", unsafe_allow_html=True)
    cats = get_category_map()
    s1, s2 = st.columns([2,1])
    with s1:
        query = st.text_input("Search", placeholder="Search_
