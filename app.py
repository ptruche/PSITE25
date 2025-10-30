# app.py
import streamlit as st
import pandas as pd

from psite_core import (
    get_topics,
    get_category_map,
    load_questions_for_subjects,
    questions_count_by_topic,
    debug_questions_index,
)

st.set_page_config(page_title="PSITE Mastery", layout="wide")

# ======== Minimal clean styles (prevents header clipping) ========
st.markdown("""
<style>
:root { --border:#eef0f3; --accent:#1d4ed8; }
header { visibility:hidden; height:0 !important; }
.block-container { padding-top: 0.6rem !important; }
.section-title { font-weight:700; margin:.25rem 0 .5rem 0; }
.card { border:1px solid var(--border); border-radius:14px; padding:12px; background:#fff; }
.topic-pill { border:1px solid #dbe2ea; border-radius:999px; padding:.18rem .55rem; font-size:.82rem; background:#f7f9fc; }
.badge { background:#eef2ff; color:#3730a3; border-radius:999px; padding:.1rem .45rem; font-size:.75rem; }
.qprompt { border:1px solid var(--border); background:#fafbfc; border-radius:10px; padding:12px; margin-bottom:8px; }
.verdict-ok { background:#10b9811a; color:#065f46; border:1px solid #34d399; border-radius:999px; padding:.18rem .5rem; display:inline-block; }
.verdict-err { background:#ef44441a; color:#7f1d1d; border:1px solid #fca5a5; border-radius:999px; padding:.18rem .5rem; display:inline-block; }
</style>
""", unsafe_allow_html=True)

# ======== Sidebar ========
with st.sidebar:
    st.markdown("### Navigation")
    page = st.radio("", ["Dashboard", "Make a Quiz", "All Topics", "Debug"], label_visibility="collapsed")

# ======== Helpers ========
ALL_TOPICS = get_topics()
COUNTS = questions_count_by_topic()

def topic_badge(t: str) -> str:
    n = COUNTS.get(t, 0)
    return f"<span class='badge'>{n} q</span>"

# ======== Dashboard ========
if page == "Dashboard":
    st.markdown("## PSITE Mastery")
    st.write("Welcome. Use **Make a Quiz** to start practicing, or **All Topics** to browse topics and launch a quiz by topic.")
    # Quick summary of counts
    total_q = sum(COUNTS.values())
    st.markdown(f"**Discovered questions:** {total_q} across **{sum(1 for v in COUNTS.values() if v>0)}** topics.")

# ======== Make a Quiz ========
elif page == "Make a Quiz":
    st.markdown("## Make a Quiz")
    cat_map = get_category_map()
    with st.expander("Pick topics (optional)", expanded=False):
        for cat, topics in cat_map.items():
            st.markdown(f"**{cat}**")
            cols = st.columns(3)
            picks = []
            for i, t in enumerate(topics):
                with cols[i % 3]:
                    st.checkbox(f"{t}", key=f"pick_{t}")
    # Gather selected topics
    selected = [t for t in ALL_TOPICS if st.session_state.get(f"pick_{t}")]
    df = load_questions_for_subjects(selected)
    total = len(df)
    st.caption(f"Pool size: {total} questions")
    n = st.number_input("How many questions?", min_value=1 if total else 0, max_value=max(1,total), value=min(20, max(1,total)), step=1)
    go = st.button("Start ▶")
    if go:
        if df.empty:
            st.warning("No questions found for the current selection.")
        else:
            pool = (df.sample(n=int(n), random_state=42).reset_index(drop=True)
                    if len(df) > n else df.sample(frac=1.0, random_state=42).reset_index(drop=True))
            st.session_state.pool = pool
            st.session_state.idx = 0
            st.session_state.revealed = set()
            st.session_state.answers = {}

# ======== All Topics ========
elif page == "All Topics":
    st.markdown("## All Topics")
    cat_map = get_category_map()
    for cat, topics in cat_map.items():
        st.markdown(f"### {cat}")
        for t in topics:
            n = COUNTS.get(t, 0)
            c1, c2, c3 = st.columns([6,2,2])
            with c1:
                st.markdown(f"- **{t}** &nbsp; {topic_badge(t)}", unsafe_allow_html=True)
            with c2:
                if st.button("Make quiz", key=f"mk_{t}"):
                    df = load_questions_for_subjects([t])
                    if df.empty:
                        st.warning(f"No questions found for: {t}")
                    else:
                        st.session_state.pool = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
                        st.session_state.idx = 0
                        st.session_state.revealed = set()
                        st.session_state.answers = {}
                        st.success(f"Quiz ready from {t} — switch to **Make a Quiz** to start.")
            with c3:
                st.write("")  # reserved for future "Review" link if you add review pages later
        st.markdown("---")

# ======== Debug ========
else:
    st.markdown("## Debug: Question Index")
    st.info("Use this page to confirm the app is seeing your question files. If everything is 0, check the folder path and filenames.")
    st.dataframe(debug_questions_index(), use_container_width=True, hide_index=True)

# ======== Quiz Runner (appears anywhere if a pool exists) ========
pool = st.session_state.get("pool")
if pool is not None and not pool.empty:
    st.markdown("## Quiz")
    i = st.session_state.get("idx", 0)
    row = pool.iloc[i]
    st.markdown(f"<div class='qprompt'>{row['stem']}</div>", unsafe_allow_html=True)
    letters = ["A","B","C","D","E"]
    sel = st.radio("Select one:", letters, format_func=lambda L: row[L], index=letters.index(st.session_state.get("answers",{}).get(row["id"], letters[0])) if st.session_state.get("answers",{}).get(row["id"]) in letters else 0, key=f"q_{row['id']}")
    st.session_state.setdefault("answers", {})[row["id"]] = sel

    cols = st.columns([1,1,1,6])
    with cols[0]:
        if st.button("Reveal"):
            st.session_state.setdefault("revealed", set()).add(row["id"])
    with cols[1]:
        if st.button("Prev", disabled=(i==0)):
            st.session_state["idx"] = max(0, i-1); st.rerun()
    with cols[2]:
        if st.button("Next", disabled=(i==len(pool)-1)):
            st.session_state["idx"] = min(len(pool)-1, i+1); st.rerun()

    # verdict + explanation
    if row["id"] in st.session_state.get("revealed", set()):
        verdict = "verdict-ok" if sel == row["correct"] else "verdict-err"
        st.markdown(f"<span class='{verdict}'>{'Correct' if sel==row['correct'] else 'Incorrect'}</span>", unsafe_allow_html=True)
        if str(row["explanation"]).strip():
            st.markdown("---")
            st.markdown(row["explanation"])
