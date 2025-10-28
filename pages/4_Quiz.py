import streamlit as st
import pandas as pd
from psite_core import (
    apply_base_theme, ensure_session_keys, load_questions_for_subjects,
    load_questions_frame, update_topic_stats
)

st.set_page_config(page_title="Quiz — PSITE Mastery", layout="wide")
apply_base_theme()
ensure_session_keys()

topic = st.session_state.get("active_topic")

def build_pool():
    if topic:
        df = load_questions_for_subjects([topic])
    else:
        df = load_questions_frame()
    return df.sample(frac=1.0, random_state=42).reset_index(drop=True) if not df.empty else df

if st.session_state.get("quiz_pool") is None:
    st.session_state.quiz_pool = build_pool()
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
    st.markdown("<div class='psite-title'>Quiz</div>", unsafe_allow_html=True)
with hdr[2]:
    if st.button("Restart"):
        st.session_state.quiz_pool = build_pool()
        st.session_state.quiz_idx = 0
        st.session_state.quiz_finished = False
        st.session_state.quiz_answers = {}
        st.session_state.quiz_revealed = set()
        st.rerun()

if pool is None or pool.empty:
    st.info("No questions found. Add .md questions to `data/questions/`.")
    st.stop()

i = st.session_state.quiz_idx
row = pool.iloc[i]

pct = int(((i + 1) / len(pool)) * 100)
st.progress(pct / 100)
st.caption(f"Question {i+1} of {len(pool)}" + (f"  •  Topic: {topic}" if topic else ""))

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

if row["id"] in st.session_state.quiz_revealed:
    is_correct = (choice == row["correct"])
    st.info("✅ Correct" if is_correct else f"❌ Incorrect — Correct is {row['correct']}")
    if row["explanation"].strip():
        st.markdown(row["explanation"])
    if not st.session_state.get(f"scored_{row['id']}", False):
        update_topic_stats(row["subject"], is_correct)
        st.session_state[f"scored_{row['id']}"] = True

if st.session_state.quiz_finished:
    correct_n = sum(
        1 for qid, ans in st.session_state.quiz_answers.items()
        if pool.set_index("id").loc[qid]["correct"] == ans and qid in st.session_state.quiz_revealed
    )
    revealed_n = sum(1 for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed)
    st.success(f"Score: {correct_n}/{revealed_n if revealed_n else len(pool)}")
