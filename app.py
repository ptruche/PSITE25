import streamlit as st
import pandas as pd
from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, resolve_review_path, load_questions_for_subjects,
    load_questions_frame, update_topic_stats, sr_due_ids, sr_update
)

st.set_page_config(page_title="PSITE Mastery", page_icon=None, layout="wide")
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()   # <-- restore from cookie or URL token

# ---------- Fixed header (prevents clipping; logout lives here) ----------
st.markdown("""
<div class="app-header">
  <div class="app-header-inner">
    <div class="app-brand">
      <div class="app-title">PSITE Mastery</div>
      <div class="app-sub">Practice • Review • Analytics</div>
    </div>
    <div id="logout-slot"></div>
  </div>
</div>
""", unsafe_allow_html=True)

right_anchor = st.columns([1,8,1])[0]
with right_anchor:
    if auth_is_authed():
        auth_logout_button()

# ---------- Login gate ----------
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access topics, reviews, and quizzes.")
    auth_login_form()
    st.stop()

# ---------- Sidebar: Topics & Quiz launcher ----------
with st.sidebar:
    st.markdown("### Topics")
    cats = get_category_map()
    chip_cols = st.columns(3)
    i = 0
    for cat, topics in cats.items():
        st.caption(cat)
        for t in topics:
            with chip_cols[i % 3]:
                if st.button(t, key=f"chip_{t}", use_container_width=True):
                    st.session_state.active_topic = t
                    st.session_state.view = "review"
                    st.rerun()
            i += 1

    st.markdown("---")
    st.markdown("### Start a Quiz")
    mode = st.radio("Mode", ["normal","spaced","weakest"], horizontal=True, label_visibility="collapsed")
    st.session_state.quiz_mode = mode
    num = st.number_input("Number of questions (normal/weakest)", 5, 50, 20, step=5, help="Ignored for spaced repetition.")
    if st.button("Start ▶", use_container_width=True):
        if mode == "normal":
            subjects = [st.session_state.active_topic] if st.session_state.get("active_topic") else []
            df = load_questions_for_subjects(subjects) if subjects else load_questions_frame()
            pool = df.sample(n=min(len(df), int(num)), random_state=42).reset_index(drop=True) if not df.empty else df
        elif mode == "spaced":
            ids = sr_due_ids(limit=50, subjects=None)
            df_all = load_questions_frame()
            pool = df_all[df_all["id"].isin(ids)].reset_index(drop=True) if not df_all.empty else df_all
        else:
            df_all = load_questions_frame()
            pool = df_all.sample(n=min(len(df_all), int(num)), random_state=42).reset_index(drop=True) if not df_all.empty else df_all

        st.session_state.quiz_pool = pool
        st.session_state.quiz_idx = 0
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.session_state.quiz_finished = False
        st.session_state.view = "quiz"
        st.rerun()

# ---------- Main area ----------
def render_review(topic: str):
    st.markdown(f"### {topic}")
    p = resolve_review_path(topic)
    if not p:
        st.info("No review uploaded yet. Place a `.md` file in `data/reviews/` named after this topic (slugified).")
        return
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    st.markdown(f"<div class='explain-scope'>{txt}</div>", unsafe_allow_html=True)

def render_topics_grid():
    st.markdown("### All Topics")
    cats = get_category_map()
    chip_cols = st.columns(3)
    i = 0
    for cat, topics in cats.items():
        st.caption(cat)
        for t in topics:
            with chip_cols[i % 3]:
                if st.button(t, key=f"grid_{t}", use_container_width=True):
                    st.session_state.active_topic = t
                    st.session_state.view = "review"
                    st.rerun()
            i += 1

def render_quiz():
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("✅ No SR items due right now.")
        else:
            st.info("No questions found. Add `.md` files to `data/questions/`.")
        return

    i = st.session_state.get("quiz_idx", 0)
    row = pool.iloc[i]
    pct = int(((i + 1) / len(pool)) * 100)
    st.progress(pct/100)
    suffix = f" • Topic: {row.get('subject','')}" if row.get("subject") else ""
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

# View switch
view = st.session_state.get("view", "topics")
if view == "review":
    back, _ = st.columns([1,8])
    with back:
        if st.button("← All Topics", type="secondary"):
            st.session_state.view = "topics"; st.rerun()
    render_review(st.session_state.get("active_topic") or "")
elif view == "quiz":
    render_quiz()
else:
    render_topics_grid()
