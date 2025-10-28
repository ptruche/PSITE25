import streamlit as st
import pandas as pd
from psite_core import (
    apply_base_theme, ensure_session_keys, load_questions_for_subjects,
    load_questions_frame, update_topic_stats, sr_due_ids, sr_update,
    weakest_topics
)

st.set_page_config(page_title="Quiz — PSITE Mastery", layout="wide")
apply_base_theme()
ensure_session_keys()

topic = st.session_state.get("active_topic")
mode = st.session_state.get("quiz_mode", "normal")  # normal | spaced | weakest

def build_pool() -> pd.DataFrame:
    # NORMAL: topic-specific or all
    if mode == "normal":
        df = load_questions_for_subjects([topic]) if topic else load_questions_frame()
        return df.sample(frac=1.0, random_state=42).reset_index(drop=True) if not df.empty else df

    # SPACED: due ids, any subject (or restrict to active topic if you want)
    if mode == "spaced":
        due = sr_due_ids(limit=20, subjects=None)
        if not due:
            return pd.DataFrame(columns=["id","subject","stem","A","B","C","D","E","correct","explanation"])
        df_all = load_questions_frame()
        return df_all[df_all["id"].isin(due)].reset_index(drop=True)

    # WEAKEST: pick weakest topics and build a pool from them
    if mode == "weakest":
        w = weakest_topics(3)
        df = load_questions_for_subjects(w)
        return df.sample(frac=1.0, random_state=42).reset_index(drop=True) if not df.empty else df

    # fallback
    return load_questions_frame()

if st.session_state.get("quiz_pool") is None or st.session_state.get("quiz_pool_mode") != mode:
    st.session_state.quiz_pool = build_pool()
    st.session_state.quiz_pool_mode = mode
    st.session_state.quiz_idx = 0
    st.session_state.quiz_finished = False
    st.session_state.quiz_answers = {}
    st.session_state.quiz_revealed = set()

pool: pd.DataFrame = st.session_state.quiz_pool

hdr = st.columns([1,5,2])
with hdr[0]:
    if st.button("← Review", type="secondary"):
        st.switch_page("pages/3_Review.py")
with hdr[1]:
    title = "Quiz" if mode == "normal" else ("Spaced Repetition" if mode == "spaced" else "Weakest-Topic Quiz")
    st.markdown(f"<div class='psite-title'>{title}</div>", unsafe_allow_html=True)
with hdr[2]:
    if st.button("Restart"):
        st.session_state.quiz_pool = None
        st.rerun()

if pool is None or pool.empty:
    if mode == "spaced":
        st.success("✅ No SR items due right now. Great job!")
    else:
        st.info("No questions found. Add .md questions to `data/questions/`.")
    st.stop()

i = st.session_state.quiz_idx
row = pool.iloc[i]

pct = int(((i + 1) / len(pool)) * 100)
st.progress(pct / 100)
suffix = f"  •  Topic: {row['subject']}" if row.get("subject") else ""
st.caption(f"Question {i+1} of {len(pool)}{suffix}")

st.markdown(f"**{row['stem']}**")

letters = ["A","B","C","D","E"]
default_idx = letters.index(st.session_state.quiz_answers[row["id"]]) if row["id"] in st.session_state.quiz_answers else None
choice = st.radio("Select one:", letters, index=default_idx, format_func=lambda L: row[L],
                  label_visibility="collapsed", key=f"q_{row['id']}")
st.session_state.quiz_answers[row["id"]] = choice

cols = st.columns([1,2,2,1])
with cols[0]:
    if st.button("Reveal", key=f"rev_{i}"):
        st.session_state.quiz_revealed.add(row["id"])
with cols[1]:
    if st.button("Previous", disabled=(i==0)):
        st.session_state.quiz_idx = max(0, i-1); st.rerun()
with cols[2]:
    if st.button("Next", disabled=(i==len(pool)-1)):
        st.session_state.quiz_idx = min(len(pool)-1, i+1); st.rerun()
with cols[3]:
    if st.button("Finish"):
        st.session_state.quiz_finished = True

# Feedback + bookkeeping
if row["id"] in st.session_state.quiz_revealed:
    is_correct = (choice == row["correct"])
    st.info("✅ Correct" if is_correct else f"❌ Incorrect — Correct is {row['correct']}")
    if row["explanation"].strip():
        st.markdown(row["explanation"])

    # Update mastery stats & SR schedule once per question
    if not st.session_state.get(f"scored_{row['id']}", False):
        update_topic_stats(row["subject"], is_correct)
        sr_update(row["id"], is_correct)  # <-- schedule next review
        st.session_state[f"scored_{row['id']}"] = True

# Summary
if st.session_state.quiz_finished:
    correct_n = sum(
        1 for qid, ans in st.session_state.quiz_answers.items()
        if pool.set_index("id").loc[qid]["correct"] == ans and qid in st.session_state.quiz_revealed
    )
    revealed_n = sum(1 for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed)
    st.success(f"Score: {correct_n}/{revealed_n if revealed_n else len(pool)}")
