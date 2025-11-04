# app.py
import streamlit as st
import pandas as pd
from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, get_topics, resolve_review_path,
    load_questions_frame, questions_count_by_topic, record_attempt,
    overall_accuracy, sr_due_ids, sr_update, load_progress,
    topic_to_slug, get_review_word_count,
)

# ------------------------------------------------------------------ #
# 1. Page config + theme (runs once)
# ------------------------------------------------------------------ #
st.set_page_config(
    page_title="PSITE Mastery",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# ------------------------------------------------------------------ #
# 2. Global CSS – modern, compact, dark-mode aware
# ------------------------------------------------------------------ #
st.markdown(
    """
<style>
/* ---------- ROOT ---------- */
:root {--accent:#1d4ed8; --border:#e5e7eb; --bg:#ffffff; --text:#111111; --sidebar-bg:#f9fafb;}
@media (prefers-color-scheme: dark) {
  :root {--accent:#3b82f6; --border:#374151; --bg:#111827; --text:#f9fafb; --sidebar-bg:#1f2937;}
}
html, body, [data-testid="stAppViewContainer"] {background:var(--bg); color:var(--text);}
.css-1d391kg {background:var(--bg);}

/* ---------- Layout ---------- */
[data-testid="stSidebar"] {background:var(--sidebar-bg); top:56px !important; height:calc(100vh - 56px) !important;}
[data-testid="collapsedControl"] {top:56px !important;}
[data-testid="stSidebarUserContent"] {padding:1rem 0.75rem;}
.sidebar-sep {height:1px; background:var(--border); margin:1rem 0;}
.stButton>button {width:100%; border-radius:8px; padding:.5rem .75rem; margin-bottom:.5rem; background:var(--bg); border:1px solid var(--border); transition:all 0.2s; font-weight:500;}
.stButton>button:hover {background:var(--accent); color:white; border-color:var(--accent);}

/* ---------- Sidebar toggle alignment ---------- */
[data-testid="stSidebarCollapseButton"] {position: relative; top: -56px; right: 0; z-index: 10001; background:transparent; border:none; color:var(--text);}
[data-testid="stSidebarCollapseButton"]:hover {color:var(--accent);}

/* ---------- Header (fixed) ---------- */
.app-header {position:fixed; top:0; left:0; right:0; height:56px; background:var(--bg);
  border-bottom:1px solid var(--border); display:flex; align-items:center; padding:0 1rem;
  z-index:10000; justify-content:space-between; font-weight:600;}
.app-header .logo {font-size:1.2rem; font-weight:900;}
.app-header .logo span {color:var(--accent);}

/* ---------- Main area ---------- */
.main {margin-top:56px; padding:1rem;}
.block-container {padding-top:0 !important;}

/* ---------- KPI donuts ---------- */
.kpi-card {border:1px solid var(--border); border-radius:16px; background:var(--bg);
  padding:1rem; display:flex; align-items:center; gap:1rem; box-shadow:0 1px 3px rgba(0,0,0,.05);}
.kpi-ring {width:80px; height:80px; border-radius:50%;
  background:conic-gradient(var(--accent) calc(var(--val)*1%), #e5e7eb 0);
  display:grid; place-items:center;}
.kpi-ring > div {background:var(--bg); width:54px; height:54px; border-radius:50%;
  display:grid; place-items:center; font-weight:700; font-size:1rem;}

/* ---------- Topic cards ---------- */
.topic-card {border:1px solid var(--border); border-radius:12px; background:var(--bg);
  padding:.75rem; box-shadow:0 1px 3px rgba(0,0,0,.04);}
.topic-title {font-weight:600; font-size:1rem; margin-bottom:.25rem;}
.meter {height:8px; background:#e5e7eb; border-radius:999px; overflow:hidden;}
.meter span {display:block; height:100%; background:var(--accent); width:0%;}
.badge {display:inline-flex; align-items:center; gap:4px; padding:2px 8px;
  border:1px solid var(--border); border-radius:999px; font-size:.75rem; background:var(--bg);}

/* ---------- Quiz UI ---------- */
.q-prompt {border:1px solid var(--border); background:#f9fafb; border-radius:10px;
  padding:1rem; margin-bottom:.75rem; font-size:1rem;}
.verdict {font-weight:600; padding:.2rem .6rem; border-radius:999px; display:inline-flex;}
.verdict-ok {background:#10b9811a; color:#065f46; border:1px solid #34d399;}
.verdict-err {background:#ef44441a; color:#7f1d1d; border:1px solid #fca5a5;}

/* ---------- Misc ---------- */
.section-title {font-weight:700; font-size:1.05rem; margin:.2rem 0 .5rem;}
.divider {height:1px; background:var(--border); margin:1rem 0;}
.dot {width:9px; height:9px; border-radius:50%; background:#d1d5db; display:inline-block; margin-right:6px; border:1px solid #cbd5e1; transform:translateY(1px);}
.dot.green {background:#22c55e; border-color:#22c55e;}
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ #
# 3. AUTH GATE (no st.stop() after login)
# ------------------------------------------------------------------ #
if not auth_is_authed():
    with st.container():
        st.markdown("#### Welcome to **PSITE Mastery**")
        st.caption("Sign-in to unlock your personal dashboard, spaced-repetition, and analytics.")
        auth_login_form()
    st.stop()

# ------------------------------------------------------------------ #
# 4. SESSION-LEVEL CACHING (questions are loaded **once**)
# ------------------------------------------------------------------ #
@st.cache_data(ttl=3600, show_spinner=False)
def _load_all_questions() -> pd.DataFrame:
    return load_questions_frame()

ALL_Q = _load_all_questions()

def load_questions_for_subjects(subjects: list) -> pd.DataFrame:
    if not subjects:
        return ALL_Q
    return ALL_Q[ALL_Q["subject"].isin(subjects)].reset_index(drop=True)

# ------------------------------------------------------------------ #
# 5. Helper UI bits
# ------------------------------------------------------------------ #
def _pct(n, d): return int(round(100 * n / d)) if d else 0

def _render_topic_card(topic: str):
    total = int(Q_COUNT.get(topic, 0))
    prog  = PROGRESS.get(topic, {})
    attempted = prog.get("total", 0)
    pct = _pct(attempted, total)

    rev_words = get_review_word_count(topic)
    has_review = rev_words >= 250
    has_quiz   = total >= 5

    with st.container(border=True):
        st.markdown(f"<div class='topic-title'>{topic}</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 8, 1])
        with c2:
            st.markdown(f"<div class='meter'><span style='width:{pct}%;'></span></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div style='text-align:right;font-size:.82rem;'>{pct}%</div>", unsafe_allow_html=True)

        st.markdown(
            f"<div style='display:flex;gap:.5rem;margin:.35rem 0;'>"
            f"<span class='badge'><span class='dot{' green' if has_review else ''}'></span>Review</span>"
            f"<span class='badge'><span class='dot{' green' if has_quiz else ''}'></span>Quiz</span>"
            f"<span style='margin-left:auto;font-size:.78rem;color:#6b7280'>Q: {attempted}/{total}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Review", key=f"rev_{topic}", use_container_width=True):
                st.session_state.active_topic = topic
                st.session_state.view = "review"
                st.rerun()
        with b2:
            if st.button("Quiz", key=f"quiz_{topic}", use_container_width=True):
                pool = load_questions_for_subjects([topic]).reset_index(drop=True)
                _start_quiz(pool, mode="normal", topic=topic)

# ------------------------------------------------------------------ #
# 6. Quiz engine (centralised, no duplication)
# ------------------------------------------------------------------ #
def _start_quiz(df: pd.DataFrame, mode: str = "normal", topic: str | None = None):
    st.session_state.quiz_pool = df
    st.session_state.quiz_idx = 0
    st.session_state.quiz_answers = {}
    st.session_state.quiz_revealed = set()
    st.session_state.quiz_finished = False
    st.session_state.quiz_mode = mode
    st.session_state.active_topic = topic
    st.session_state.view = "quiz"
    st.rerun()

def _record_and_update(row: pd.Series, correct: bool):
    key = f"scored_{row['id']}"
    if not st.session_state.get(key, False):
        record_attempt(row.get("subject", ""), row["id"], correct)
        if st.session_state.get("quiz_mode") == "spaced":
            sr_update(row["id"], correct)
        st.session_state[key] = True

# ------------------------------------------------------------------ #
# 7. PRE-COMPUTE counts & progress (once per session)
# ------------------------------------------------------------------ #
Q_COUNT   = questions_count_by_topic()
PROGRESS  = load_progress()

# ------------------------------------------------------------------ #
# 8. LAYOUT – fixed header + sidebar
# ------------------------------------------------------------------ #
st.markdown(
    "<div class='app-header'>"
    "<div class='logo'>PSITE <span>Mastery</span></div>"
    "<div></div>"   # placeholder for future icons
    "</div>",
    unsafe_allow_html=True,
)

# Sidebar navigation
nav = {
    "Dashboard": "dashboard",
    "Score Topics": "topics",
    "Make Quiz": "make_quiz",
}
for label, view in nav.items():
    if st.sidebar.button(label, key=f"nav_{view}", use_container_width=True):
        st.session_state.view = view
        st.rerun()

st.sidebar.markdown("<div class='sidebar-sep'></div>", unsafe_allow_html=True)

if st.sidebar.button("Spaced Repetition", key="nav_sr", use_container_width=True):
    ids = sr_due_ids(limit=50)
    pool = ALL_Q[ALL_Q["id"].isin(ids)].reset_index(drop=True) if not ALL_Q.empty else ALL_Q
    _start_quiz(pool, mode="spaced")

st.sidebar.markdown("<div class='sidebar-sep'></div>", unsafe_allow_html=True)
if st.sidebar.button("Logout", type="secondary", use_container_width=True):
    clear_persisted_login()
    st.rerun()

# ---------- MAIN ----------
st.markdown("<div class='main'>", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# 9. VIEW ROUTER
# ------------------------------------------------------------------ #
view = st.session_state.get("view", "dashboard")

# ---------- DASHBOARD ----------
if view == "dashboard":
    st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
    attempted_all = sum(v.get("total", 0) for v in PROGRESS.values())
    total_all = sum(Q_COUNT.get(t, 0) for t in Q_COUNT)
    pct_done = _pct(attempted_all, total_all)
    pct_acc  = int(round(overall_accuracy() * 100))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-ring" style="--val:{pct_done};"><div>{pct_done}%</div></div>
              <div style="display:flex;flex-direction:column;gap:2px;">
                <div style="font-weight:600;font-size:.95rem;">Completed</div>
                <div style="font-size:.82rem;color:#6b7280">{attempted_all} of {total_all}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-ring" style="--val:{pct_acc};"><div>{pct_acc}%</div></div>
              <div style="display:flex;flex-direction:column;gap:2px;">
                <div style="font-weight:600;font-size:.95rem;">Accuracy</div>
                <div style="font-size:.82rem;color:#6b7280">All attempts</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------- TOPICS ----------
elif view == "topics":
    st.markdown("<div class='section-title'>Score Topics</div>", unsafe_allow_html=True)

    cats = get_category_map()
    s1, s2 = st.columns([2, 1])
    with s1:
        q = st.text_input("Search topics", placeholder="Search…", label_visibility="collapsed").strip().lower()
    with s2:
        cat_names = ["All"] + list(cats.keys())
        chosen_cat = st.selectbox("Category", cat_names, index=0, label_visibility="collapsed")

    topics = []
    for cat, arr in cats.items():
        if chosen_cat != "All" and cat != chosen_cat:
            continue
        for t in arr:
            if q and q not in t.lower():
                continue
            topics.append(t)

    if not topics:
        st.info("No topics match your filter.")
    else:
        cols = st.columns(3)
        for i, t in enumerate(topics):
            with cols[i % 3]:
                _render_topic_card(t)

# ---------- REVIEW ----------
elif view == "review":
    topic = st.session_state.get("active_topic")
    if not topic:
        st.info("Select a topic from **Score Topics**.")
    else:
        st.markdown(f"<div class='section-title'>{topic}</div>", unsafe_allow_html=True)
        path = resolve_review_path(topic)
        if not path:
            st.info("No review file yet – add a `.md` inside `data/reviews/` with the topic slug.")
        else:
            with open(path, "r", encoding="utf-8") as f:
                st.markdown(f.read(), unsafe_allow_html=True)

        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        if st.button("Quiz this topic ▶", use_container_width=True):
            pool = load_questions_for_subjects([topic]).reset_index(drop=True)
            _start_quiz(pool, mode="normal", topic=topic)

# ---------- MAKE QUIZ ----------
elif view == "make_quiz":
    st.markdown("<div class='section-title'>Make a Quiz</div>", unsafe_allow_html=True)
    topics = ["Any"] + get_topics()
    pick = st.multiselect("Choose topics (leave empty → Any)", topics, default=[])
    n = st.number_input("Questions", 5, 100, 20, step=5)
    if st.button("Start ▶", use_container_width=True):
        sel = [] if ("Any" in pick or not pick) else pick
        df = load_questions_for_subjects(sel)
        df = df.sample(n=min(len(df), int(n)), random_state=42).reset_index(drop=True)
        _start_quiz(df, mode="normal")

# ---------- QUIZ ----------
elif view == "quiz":
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        st.info("No questions available for the selected mode.")
    else:
        i = st.session_state.quiz_idx
        row = pool.iloc[i]
        pct = int(((i + 1) / len(pool)) * 100)
        st.progress(pct / 100)
        suffix = f" • {row.get('subject','')}" if row.get("subject") else ""
        st.caption(f"Question {i+1} of {len(pool)}{suffix}")

        st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

        letters = ["A", "B", "C", "D", "E"]
        prev = st.session_state.quiz_answers.get(row["id"])
        default = letters.index(prev) if prev in letters else 0
        choice = st.radio(
            "", letters, index=default,
            format_func=lambda L: row[L],
            label_visibility="collapsed",
            key=f"q_{row['id']}"
        )
        st.session_state.quiz_answers[row["id"]] = choice

        c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
        with c1:
            if st.button("Reveal", key=f"rev_{i}"):
                st.session_state.quiz_revealed.add(row["id"])
        with c2:
            if st.button("Previous", disabled=i == 0):
                st.session_state.quiz_idx = i - 1
                st.rerun()
        with c3:
            if st.button("Next", disabled=i == len(pool) - 1):
                st.session_state.quiz_idx = i + 1
                st.rerun()
        with c4:
            if st.button("Finish"):
                st.session_state.quiz_finished = True

        # ---- REVEAL ----
        if row["id"] in st.session_state.quiz_revealed:
            correct = (choice == row["correct"])
            verdict = "verdict-ok" if correct else "verdict-err"
            txt = "Correct" if correct else "Incorrect"
            st.markdown(f"<span class='verdict {verdict}'>{txt}</span>", unsafe_allow_html=True)
            if row.get("explanation"):
                st.markdown(row["explanation"], unsafe_allow_html=True)
            _record_and_update(row, correct)

        # ---- FINISH ----
        if st.session_state.quiz_finished:
            scored = [qid for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed]
            correct_n = sum(1 for qid in scored if pool.set_index("id").loc[qid, "correct"] == st.session_state.quiz_answers[qid])
            denom = len(scored) or len(pool)
            st.success(f"Score: {correct_n}/{denom}")

st.markdown("</div>", unsafe_allow_html=True)   # .main
