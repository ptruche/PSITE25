# app.py
import streamlit as st
import pandas as pd
from typing import Dict

from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, get_topics, resolve_review_path,
    load_questions_for_subjects, load_questions_frame,
    questions_count_by_topic, record_attempt, overall_accuracy,
    accuracy_timeseries, topic_strengths, sr_due_ids, sr_update,
    load_progress, slugify
)

# ============ App Shell / Theme ============
st.set_page_config(page_title="PSITE Mastery", page_icon=None, layout="wide", initial_sidebar_state="expanded")
apply_base_theme()

# IMPORTANT: initialize session + restore token BEFORE auth gate
ensure_session_keys()
try_auto_login_persisted()

# ============ Small helpers (UI) ============
def _hstack(*cols):
    return st.columns(cols)

def _pct_int(x):
    try: return int(round(float(x)*100))
    except Exception: return 0

def _review_word_count(topic: str) -> int:
    """Return word count of the review markdown for topic (0 if none)."""
    p = resolve_review_path(topic)
    if not p:
        return 0
    try:
        with open(p, "r", encoding="utf-8") as f:
            txt = f.read()
        # very simple word count
        return len(txt.split())
    except Exception:
        return 0

def _topic_card(topic: str, q_total_map: Dict[str, int], progress_map: Dict[str, Dict]):
    """Single bubble with title, progress meter, and two small buttons."""
    total_q = q_total_map.get(topic, 0)
    attempted = progress_map.get(topic, {}).get("total", 0)
    pct_done = int(100 * attempted / total_q) if total_q else 0

    # Button styles based on availability
    rev_words = _review_word_count(topic)
    has_good_review = rev_words >= 250
    has_enough_q = total_q >= 5

    rev_button_style = (
        "background:#10b981; color:#fff; border:1px solid #0ea56f;"
        if has_good_review else
        "background:#fff; color:#111; border:1px solid #dbe2ea;"
    )
    quiz_button_style = (
        "background:#10b981; color:#fff; border:1px solid #0ea56f;"
        if has_enough_q else
        "background:#fff; color:#111; border:1px solid #dbe2ea;"
    )

    slug = slugify(topic)
    st.markdown(f"""
    <div class="topic-card" style="gap:.55rem;">
      <div class="topic-title">{topic}</div>
      <div class="topic-row">
        <div class="meter"><span style="width:{pct_done}%"></span></div>
        <div style="width:46px;text-align:right;font-size:.85rem;">{pct_done}%</div>
      </div>
      <div style="display:flex; gap:.4rem; align-items:center;">
        <button id="rev_{slug}" style="padding:.38rem .6rem; border-radius:10px; {rev_button_style} cursor:pointer;">Review</button>
        <button id="quiz_{slug}" style="padding:.38rem .6rem; border-radius:10px; {quiz_button_style} cursor:pointer;">Quiz</button>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Wire up the buttons with invisible Streamlit buttons (keys)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Review", key=f"rev_btn_{slug}", help=f"Open review: {topic}", use_container_width=True):
            st.session_state.active_topic = topic
            st.session_state.view = "review"
            st.rerun()
    with c2:
        if st.button("Quiz", key=f"quiz_btn_{slug}", help=f"Start quiz: {topic}", use_container_width=True):
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

# ============ Auth gate ============
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, and quizzes.")
    auth_login_form()
    st.stop()

# ============ Sidebar ============
with st.sidebar:
    st.markdown("### Navigate")
    if st.button("Dashboard", use_container_width=True):
        st.session_state.view = "dashboard"
        st.rerun()
    if st.button("Score Topics", use_container_width=True):
        st.session_state.view = "topics"
        st.rerun()
    if st.button("Make Quiz", use_container_width=True):
        st.session_state.view = "make_quiz"
        st.rerun()
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
    st.markdown("---")
    auth_logout_button()

# ============ Views ============
def view_dashboard():
    st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
    acc = overall_accuracy()  # 0..1
    acc_pct = _pct_int(acc)

    # progress circle stand-ins (clean text + progress bars)
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        st.metric("Overall Correct", f"{acc_pct}%")
        st.progress(acc)
    # Completion proxy (% attempted / total questions)
    prog = load_progress()
    q_total_map = questions_count_by_topic()
    attempted_sum = sum(v.get("total", 0) for v in prog.values())
    total_q_sum = sum(q_total_map.values()) or 1
    completion = attempted_sum / total_q_sum
    with c2:
        st.metric("Completion", f"{_pct_int(completion)}%")
        st.progress(completion)
    # Average questions/day from 30-day series
    series = accuracy_timeseries(days=30)
    avg_per_day = 0
    if series:
        avg_per_day = int(round(sum(n for _, _, n in series)/len(series)))
    with c3:
        st.metric("Avg Q/day (30d)", f"{avg_per_day}")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    if series:
        # Streamlit-native charts (no matplotlib)
        dates = [d for d, _, _ in series]
        accs = [a for _, a, _ in series]
        counts = [n for _, _, n in series]
        df_acc = pd.DataFrame({"date": dates, "accuracy": [x*100 for x in accs]}).set_index("date")
        df_cnt = pd.DataFrame({"date": dates, "attempts": counts}).set_index("date")
        st.markdown("**Last 30 days — Accuracy (%)**")
        st.line_chart(df_acc)
        st.markdown("**Last 30 days — Attempts**")
        st.bar_chart(df_cnt)
    else:
        st.info("No attempts yet. Start a quiz to build your trend.")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    strong, weak = topic_strengths(k=5)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Strongest topics**")
        if not strong: st.caption("—")
        for t, a, n in strong:
            st.write(f"{t} — {int(a*100)}% ({n} q)")
    with c2:
        st.markdown("**Weakest topics**")
        if not weak: st.caption("—")
        for t, a, n in weak:
            st.write(f"{t} — {int(a*100)}% ({n} q)")

def view_topics():
    st.markdown("<div class='section-title'>Score Topics</div>", unsafe_allow_html=True)
    cats = get_category_map()
    q_count = questions_count_by_topic()
    prog = load_progress()

    # Top tabs for categories (clean + readable)
    cat_names = list(cats.keys())
    tabs = st.tabs(cat_names)
    for tab, cat in zip(tabs, cat_names):
        with tab:
            st.caption(f"{cat}")
            topics = cats[cat]
            if not topics:
                st.info("No topics in this category.")
                continue
            cols = st.columns(3)
            i = 0
            for t in topics:
                with cols[i % 3]:
                    _topic_card(t, q_count, prog)
                i += 1

def view_review():
    # Stay logged in; only route here if authed
    topic = st.session_state.get("active_topic") or ""
    if not topic:
        st.info("Choose a topic from Score Topics.")
        return
    st.markdown(f"<div class='section-title'>{topic}</div>", unsafe_allow_html=True)
    p = resolve_review_path(topic)
    if not p:
        st.info("No review uploaded yet. Place a `.md` file in `data/reviews/` named after this topic (slugified).")
        return
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    # Render the raw markdown review
    st.markdown(txt, unsafe_allow_html=True)

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    if st.button("Quiz this topic ▶", use_container_width=True):
        df = load_questions_for_subjects([topic])
        st.session_state.quiz_pool = df.reset_index(drop=True)
        st.session_state.quiz_idx = 0
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.session_state.quiz_finished = False
        st.session_state.quiz_mode = "normal"
        st.session_state.view = "quiz"
        st.rerun()

def view_make_quiz():
    st.markdown("<div class='section-title'>Make a Quiz</div>", unsafe_allow_html=True)
    topics = ["Any"] + get_topics()
    pick = st.multiselect("Choose topics (or leave empty for Any):", topics, default=[])
    n = st.number_input("Number of questions", 5, 100, 20, step=5)
    if st.button("Start ▶", use_container_width=True):
        if pick and "Any" in pick:
            pick = []
        df = load_questions_for_subjects(pick)
        df = df.sample(n=min(len(df), int(n)), random_state=42).reset_index(drop=True) if not df.empty else df
        st.session_state.quiz_pool = df
        st.session_state.quiz_idx = 0
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.session_state.quiz_finished = False
        st.session_state.quiz_mode = "normal"
        st.session_state.view = "quiz"
        st.rerun()

def view_quiz():
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("✅ No spaced-repetition items due.")
        else:
            st.info("No questions found. Add `.md` files under `data/questions/<topic-slug>/`.")
        return

    i = st.session_state.get("quiz_idx", 0)
    row = pool.iloc[i]
    pct = int(((i + 1) / len(pool)) * 100)
    st.progress(pct/100)
    suffix = f" • {row.get('subject','')}" if row.get('subject') else ""
    st.caption(f"Question {i+1} of {len(pool)}{suffix}")

    st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

    letters = ["A","B","C","D","E"]
    prev_choice = st.session_state.quiz_answers.get(row["id"])
    default_idx = letters.index(prev_choice) if prev_choice in letters else 0
    choice = st.radio("",
                      letters,
                      index=default_idx,
                      format_func=lambda L: row[L],
                      label_visibility="collapsed",
                      key=f"q_{row['id']}")
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
        verdict_html = (
            "<span class='verdict verdict-ok'>Correct</span>"
            if is_correct else
            "<span class='verdict verdict-err'>Incorrect</span>"
        )
        st.markdown(verdict_html, unsafe_allow_html=True)
        if str(row.get("explanation","")).strip():
            st.markdown(row["explanation"], unsafe_allow_html=True)
        # log once per question id
        key = f"scored_{row['id']}"
        if not st.session_state.get(key, False):
            record_attempt(row.get("subject",""), row["id"], is_correct)
            if st.session_state.get("quiz_mode") == "spaced":
                sr_update(row["id"], is_correct)
            st.session_state[key] = True

    if st.session_state.quiz_finished:
        # Score only revealed questions
        idxed = pool.set_index("id")
        scored_ids = [qid for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed]
        correct_n = sum(1 for qid in scored_ids if idxed.loc[qid]["correct"] == st.session_state.quiz_answers[qid])
        denom = len(scored_ids) if scored_ids else len(pool)
        st.success(f"Score: {correct_n}/{denom}")

# ============ Router ============
view = st.session_state.get("view", "dashboard")
if view == "topics":
    view_topics()
elif view == "review":
    view_review()
elif view == "make_quiz":
    view_make_quiz()
elif view == "quiz":
    view_quiz()
else:
    view_dashboard()
