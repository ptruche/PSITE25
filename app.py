# app.py
import streamlit as st
import pandas as pd
import datetime
from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, clear_persisted_login,
    get_category_map, get_topics, resolve_review_path,
    load_questions_frame, questions_count_by_topic, record_attempt,
    overall_accuracy, sr_due_ids, sr_update, load_progress,
    topic_to_slug, get_review_word_count, load_history
)

# ------------------------------------------------------------------ #
# 1. Page config + theme (runs once)
# ------------------------------------------------------------------ #
st.set_page_config(
    page_title="PSITE Mastery",
    page_icon="https://i.fbcd.co/products/resized/resized-750-500/s005e-26-e07-mainpreview-11f76902af216746cd69fefb519f397472ae3f992e346a94a460aba7664c0a5b.jpg",
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
:root {--accent:#1d4ed8; --border:#e5e7eb; --bg:#ffffff; --text:#111111; --sidebar-bg:linear-gradient(to bottom, #f9fafb, #e5e7eb); --shadow:0 1px 3px rgba(0,0,0,0.05); --text-muted:#6b7280;}
@media (prefers-color-scheme: dark) {
  :root {--accent:#3b82f6; --border:#374151; --bg:#111827; --text:#f9fafb; --sidebar-bg:linear-gradient(to bottom, #1f2937, #111827); --shadow:0 1px 3px rgba(0,0,0,0.2); --text-muted:#9ca3af;}
}
html, body, [data-testid="stAppViewContainer"] {background:var(--bg); color:var(--text);}
.css-1d391kg {background:var(--bg);}

/* ---------- Layout ---------- */
[data-testid="stSidebar"] {background:var(--sidebar-bg); top:56px !important; height:calc(100vh - 56px) !important; box-shadow:var(--shadow); border-right:1px solid var(--border);}
[data-testid="collapsedControl"] {top:56px !important; height:56px !important; justify-content:center; align-items:center; color:var(--text); font-size:1.2rem;}
[data-testid="collapsedControl"]:hover {color:var(--accent);}
[data-testid="stSidebarCollapseButton"] {justify-content:flex-end; height:56px !important; align-items:center; display:flex; width:100%; color:var(--text); font-size:1.2rem; padding-right:1rem;}
[data-testid="stSidebarCollapseButton"]:hover {color:var(--accent);}
[data-testid="stSidebarUserContent"] {padding:1.5rem 1.25rem;}
.sidebar-sep {height:1px; background:var(--border); margin:1.5rem 0;}
.stButton>button {width:100%; border-radius:6px; padding:.55rem 1rem; margin-bottom:.75rem; background:transparent; border:1px solid var(--border); transition:all 0.2s ease; font-weight:500; color:var(--text); box-shadow:var(--shadow);}
.stButton>button:hover {background:var(--accent); color:white; border-color:var(--accent); box-shadow:0 4px 12px rgba(0,0,0,0.1); transform:translateY(-1px);}

/* ---------- Header (fixed) ---------- */
.app-header {position:fixed; top:0; left:0; right:0; height:56px; background:var(--bg);
  border-bottom:1px solid var(--border); display:flex; align-items:center; padding:0 1.5rem;
  z-index:10000; justify-content:space-between; font-weight:600; box-shadow:var(--shadow);}
.app-header .logo {font-size:1.2rem; font-weight:900;}
.app-header .logo span {color:var(--accent);}

/* ---------- Main area ---------- */
.main {margin-top:56px; padding:1.5rem;}
.block-container {padding-top:0 !important;}

/* ---------- KPI donuts ---------- */
.kpi-card {border:1px solid var(--border); border-radius:16px; background:var(--bg);
  padding:1.25rem; display:flex; align-items:center; gap:1.25rem; box-shadow:var(--shadow);}
.kpi-ring {width:80px; height:80px; border-radius:50%;
  background:conic-gradient(var(--accent) calc(var(--val)*1%), #e5e7eb 0);
  display:grid; place-items:center;}
.kpi-ring > div {background:var(--bg); width:54px; height:54px; border-radius:50%;
  display:grid; place-items:center; font-weight:700; font-size:1rem;}

/* ---------- Topic cards ---------- */
.topic-card {border:1px solid var(--border); border-radius:12px; background:var(--bg);
  padding:1rem; box-shadow:var(--shadow);}
.topic-title {font-weight:600; font-size:1rem; margin-bottom:.35rem;}
.meter {height:8px; background:#e5e7eb; border-radius:999px; overflow:hidden;}
.meter span {display:block; height:100%; background:var(--accent); width:0%;}
.badge {display:inline-flex; align-items:center; gap:6px; padding:.25rem .75rem;
  border:1px solid var(--border); border-radius:999px; font-size:.8rem; background:var(--bg);}

/* ---------- Quiz UI ---------- */
.q-prompt {border:1px solid var(--border); background:#f9fafb; border-radius:10px;
  padding:1.25rem; margin-bottom:1rem; font-size:1rem;}
.verdict {font-weight:600; padding:.25rem .75rem; border-radius:999px; display:inline-flex;}
.verdict-ok {background:#10b9811a; color:#065f46; border:1px solid #34d399;}
.verdict-err {background:#ef44441a; color:#7f1d1d; border:1px solid #fca5a5;}

/* ---------- Misc ---------- */
.section-title {font-weight:700; font-size:1.05rem; margin:.2rem 0 .5rem;}
.divider {height:1px; background:var(--border); margin:1rem 0;}
.dot {width:9px; height:9px; border-radius:50%; background:#d1d5db; display:inline-block; margin-right:6px; border:1px solid #cbd5e1; transform:translateY(1px);}
.dot.green {background:#22c55e; border-color:#22c55e;}
.last-attempt {font-size:0.85rem; color:var(--text-muted); margin-bottom:1rem;}
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
    st.session_state.quiz_status = {}  # To track correct/wrong per qid
    st.rerun()

def _record_and_update(row: pd.Series, correct: bool):
    key = f"scored_{row['id']}"
    if not st.session_state.get(key, False):
        record_attempt(row.get("subject", ""), row["id"], correct)
        if st.session_state.get("quiz_mode") == "spaced":
            sr_update(row["id"], correct)
        st.session_state[key] = True
    st.session_state.quiz_status[row["id"]] = correct

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
        st.info("Choose a topic from Score Topics.")
    else:
        st.markdown(f"<div class='section-title'>{topic}</div>", unsafe_allow_html=True)
        p = resolve_review_path(topic)
        if not p:
            st.info("No review uploaded yet. Place a `.md` file in `data/reviews/` named with the topic slug.")
        else:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read()
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

# ---------- MAKE QUIZ ----------
elif view == "make_quiz":
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

# ---------- QUIZ ----------
elif view == "quiz":
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("✅ No spaced-repetition items due.")
        else:
            st.info("No questions found. Add `.md` files to `data/questions/`.")
    else:
        history = load_history()

        st.markdown("<div class='section-title'>Quiz</div>", unsafe_allow_html=True)

        # Question navigator on right
        left, right = st.columns([9,1])
        with right:
            st.markdown("<div class='q-nav'>", unsafe_allow_html=True)
            st.markdown("<div class='q-nav-title'>Questions</div>", unsafe_allow_html=True)
            for j in range(len(pool)):
                qid = pool.iloc[j]["id"]
                status = st.session_state.quiz_status.get(qid, None)
                btn_class = "q-nav-btn"
                if status is not None:
                    btn_class += " correct" if status else " incorrect"
                else:
                    btn_class += " unanswered"
                label = str(j+1)
                if st.button(label, key=f"nav_q_{j}", use_container_width=True):
                    st.session_state.quiz_idx = j
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with left:
            i = st.session_state.quiz_idx
            row = pool.iloc[i]
            pct = int(((i + 1) / len(pool)) * 100)
            st.progress(pct/100)
            suffix = f" • {row.get('subject','')}" if row.get('subject') else ""
            st.caption(f"Question {i+1} of {len(pool)}{suffix}")

            # Last attempt time
            q_attempts = [h for h in history if h["id"] == row["id"]]
            if q_attempts:
                last_ts = max(h["ts"] for h in q_attempts)
                last_date = datetime.datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S")
                st.markdown(f"<div class='last-attempt'>Last attempted: {last_date}</div>", unsafe_allow_html=True)

            st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

            letters = ["A","B","C","D","E"]
            prev_choice = st.session_state.quiz_answers.get(row["id"])
            default_idx = letters.index(prev_choice) if prev_choice in letters else 0
            choice = st.radio(
                "",
                letters,
                index=default_idx,
                format_func=lambda L: row[L],
                label_visibility="collapsed",
                key=f"q_{row['id']}"
            )
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
                verdict_class = "verdict-ok" if is_correct else "verdict-err"
                verdict_text = "Correct" if is_correct else "Incorrect"
                st.markdown(f"<span class='verdict {verdict_class}'>{verdict_text}</span>", unsafe_allow_html=True)
                if str(row.get("explanation","")).strip():
                    st.markdown(row["explanation"], unsafe_allow_html=True)
                _record_and_update(row, is_correct)

            if st.session_state.quiz_finished:
                idxed = pool.set_index("id")
                scored_ids = [qid for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed]
                correct_n = sum(1 for qid in scored_ids if idxed.loc[qid]["correct"] == st.session_state.quiz_answers[qid])
                denom = len(scored_ids) if scored_ids else len(pool)
                st.success(f"Score: {correct_n}/{denom}")

st.markdown("</div>", unsafe_allow_html=True)   # .main
