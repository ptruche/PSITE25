# app.py
import streamlit as st
import pandas as pd

from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, resolve_review_path, load_questions_for_subjects,
    load_questions_frame, update_topic_stats, sr_due_ids, sr_update
)

# Minimal, fixed header; sidebar opened but nearly empty
st.set_page_config(page_title="PSITE Mastery", page_icon=None, layout="wide", initial_sidebar_state="expanded")
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# ---------------- Header (simple & clean) ----------------
st.markdown("""
<div class="app-header">
  <div class="app-header-inner">
    <div class="app-brand">
      <div class="app-title">PSITE Mastery</div>
    </div>
    <div id="logout-slot"></div>
  </div>
</div>
""", unsafe_allow_html=True)

# Put Logout top-right (not in main layout flow)
rcol = st.columns([1,8,1])[0]
with rcol:
    if auth_is_authed():
        auth_logout_button()

# --------------- Login gate ---------------
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, reviews, and quizzes.")
    auth_login_form()
    st.stop()

# --------------- Sidebar: keep it minimal ---------------
with st.sidebar:
    st.markdown("#### ")
    st.caption("You can hide this menu; everything lives on the dashboard.")
    st.markdown("---")
    if auth_is_authed():
        auth_logout_button()

# ----------------- Utilities -----------------
def _topics_flat():
    cats = get_category_map()
    return [(cat, t) for cat, arr in cats.items() for t in arr]

def _topic_list():
    return [t for _, t in _topics_flat()]

def _render_topics_grid(filtered_topics):
    """Beautiful, compact grid of topics."""
    if not filtered_topics:
        st.info("No topics match your filter.")
        return
    cols_per_row = 4
    rows = (len(filtered_topics) + cols_per_row - 1) // cols_per_row
    idx = 0
    for _ in range(rows):
        cols = st.columns(cols_per_row)
        for c in cols:
            if idx >= len(filtered_topics):
                break
            topic = filtered_topics[idx]
            with c:
                st.markdown(f"""
                <div class="topic-card">
                  <div class="topic-title">{topic}</div>
                  <div class="topic-actions">
                    <button class="tiny-btn" onclick="window.parent.postMessage({{'topicSelect': {repr(topic)}}}, '*')">Review</button>
                    <button class="tiny-btn secondary" onclick="window.parent.postMessage({{'topicQuiz': {repr(topic)}}}, '*')">Quiz</button>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            idx += 1

    # Bridge buttons to Streamlit (Review / Quiz actions)
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

# ----------------- Views -----------------
def render_dashboard():
    cats = get_category_map()
    all_topics = _topic_list()

    # Quick actions row
    st.markdown("""
    <div class="section-title">Quick Actions</div>
    """, unsafe_allow_html=True)
    a, b, c = st.columns([1,1,2])
    with a:
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
    with b:
        if st.button("Random 20 ▶", use_container_width=True):
            df = load_questions_frame()
            st.session_state.quiz_pool = df.sample(n=min(len(df), 20), random_state=42).reset_index(drop=True) if not df.empty else df
            st.session_state.quiz_idx = 0
            st.session_state.quiz_answers = {}
            st.session_state.quiz_revealed = set()
            st.session_state.quiz_finished = False
            st.session_state.quiz_mode = "normal"
            st.session_state.view = "quiz"
            st.rerun()
    with c:
        st.markdown("**Topic Quiz**")
        selected = st.selectbox("Pick a topic", all_topics, label_visibility="collapsed")
        if st.button("Start ▶", use_container_width=True):
            df = load_questions_for_subjects([selected])
            st.session_state.active_topic = selected
            st.session_state.quiz_pool = df.reset_index(drop=True)
            st.session_state.quiz_idx = 0
            st.session_state.quiz_answers = {}
            st.session_state.quiz_revealed = set()
            st.session_state.quiz_finished = False
            st.session_state.quiz_mode = "normal"
            st.session_state.view = "quiz"
            st.rerun()

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # Topic browser
    st.markdown("""
    <div class="section-title">Browse Topics</div>
    """, unsafe_allow_html=True)
    s1, s2 = st.columns([2,1])
    with s1:
        query = st.text_input("Search", placeholder="Search topics…", label_visibility="collapsed").strip().lower()
    with s2:
        cat_names = ["All"] + list(cats.keys())
        cat_pick = st.selectbox("Category", cat_names, index=0, label_visibility="collapsed")

    filtered = []
    for cat, topic in _topics_flat():
        if cat_pick != "All" and cat != cat_pick:
            continue
        if query and query not in topic.lower():
            continue
        filtered.append(topic)

    _render_topics_grid(filtered)

def render_review(topic: str):
    st.markdown(f"<div class='section-title'>{topic}</div>", unsafe_allow_html=True)
    p = resolve_review_path(topic)
    if not p:
        st.info("No review uploaded yet. Place a `.md` file in `data/reviews/` named after this topic (slugified).")
        return
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    st.markdown(f"<div class='explain-scope'>{txt}</div>", unsafe_allow_html=True)

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    back, quiz = st.columns([1,1])
    with back:
        if st.button("← Browse Topics", type="secondary"):
            st.session_state.view = "dashboard"  # go back to dashboard which includes topic browser
            st.rerun()
    with quiz:
        if st.button("Quiz this topic ▶"):
            df = load_questions_for_subjects([topic])
            st.session_state.quiz_pool = df.reset_index(drop=True)
            st.session_state.quiz_idx = 0
            st.session_state.quiz_answers = {}
            st.session_state.quiz_revealed = set()
            st.session_state.quiz_finished = False
            st.session_state.quiz_mode = "normal"
            st.session_state.view = "quiz"
            st.rerun()

def render_quiz():
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("✅ No spaced-repetition items due.")
        else:
            st.info("No questions found. Add `.md` files to `data/questions/`.")
        return
    i = st.session_state.get("quiz_idx", 0)
    row = pool.iloc[i]
    pct = int(((i + 1) / len(pool)) * 100)
    st.progress(pct/100)
    suffix = f" • {row.get('subject','')}" if row.get("subject") else ""
    st.caption(f"Question {i+1} of {len(pool)}{suffix}")
    st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

    letters = ["A","B","C","D","E"]
    default_idx = letters.index(st.session_state.quiz_answers[row["id"]]) if row["id"] in st.session_state.quiz_answers else None
    choice = st.radio("", letters, index=default_idx, format_func=lambda L: row[L], label_visibility="collapsed", key=f"q_{row['id']}")
    st.session_state.quiz_answers[row["id"]] = choice

    c1, c2, c3, c4 = st.columns([1,2,2,1])
    with c1:
        if st.button("Reveal", key=f"rev_{i}"):
            st.session_state.quiz_revealed.add(row["id"])
    with c2:
        if st.button("Previous", disabled=(i==0)):
            st.session_state.quiz_idx = max(0, i-1); st.rerun()
    with c3:
        if st.button("Next", disabled=(i==len(pool)-1)):
            st.session_state.quiz_idx = min(len(pool)-1, i+1); st.rerun()
    with c4:
        if st.button("Finish"):
            st.session_state.quiz_finished = True

    if row["id"] in st.session_state.quiz_revealed:
        is_correct = (choice == row["correct"])
        st.markdown(f"<span class='verdict {'verdict-ok' if is_correct else 'verdict-err'}'>{'Correct' if is_correct else 'Incorrect'}</span>", unsafe_allow_html=True)
        if row["explanation"].strip():
            st.markdown(row["explanation"], unsafe_allow_html=True)
        if not st.session_state.get(f"scored_{row['id']}", False):
            update_topic_stats(row.get("subject",""), is_correct)
            if st.session_state.get("quiz_mode") == "spaced":
                sr_update(row["id"], is_correct)
            st.session_state[f"scored_{row['id']}"] = True

    if st.session_state.quiz_finished:
        correct_n = sum(
            1 for qid, ans in st.session_state.quiz_answers.items()
            if pool.set_index("id").loc[qid]["correct"] == ans and qid in st.session_state.quiz_revealed
        )
        revealed_n = sum(1 for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed)
        st.success(f"Score: {correct_n}/{revealed_n if revealed_n else len(pool)}")

# Router
view = st.session_state.get("view", "dashboard")
if view == "review":
    render_review(st.session_state.get("active_topic") or "")
elif view == "quiz":
    render_quiz()
else:
    render_dashboard()
