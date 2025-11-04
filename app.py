# app.py
import streamlit as st
import pandas as pd

# ----------------------------------------------------------------------
# 1. IMPORT CORE + APPLY THEME.CSS
# ----------------------------------------------------------------------
from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, get_topics, resolve_review_path,
    load_questions_for_subjects, load_questions_frame,
    questions_count_by_topic, record_attempt, overall_accuracy,
    sr_due_ids, sr_update, load_progress,
    topic_to_slug, get_review_word_count,
)

st.set_page_config(page_title="PSITE Mastery", layout="wide", initial_sidebar_state="expanded")

# Load your theme.css (exactly as you wrote it)
with open("theme.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

apply_base_theme()   # keep any extra JS you had in core

# ----------------------------------------------------------------------
# 2. SESSION / AUTH
# ----------------------------------------------------------------------
ensure_session_keys()
try_auto_login_persisted()

if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, and quizzes.")
    auth_login_form()
    st.stop()

# ----------------------------------------------------------------------
# 3. STATE HELPERS
# ----------------------------------------------------------------------
if "rail_open" not in st.session_state:
    st.session_state.rail_open = True          # default = expanded

def _toggle_rail():
    st.session_state.rail_open = not st.session_state.rail_open

def _safe_pct(numer: int, denom: int) -> int:
    return int(round(100 * numer / denom)) if denom else 0

# ----------------------------------------------------------------------
# 4. TOPIC CARD (uses your .topic-card, .tiny-btn, etc.)
# ----------------------------------------------------------------------
def _render_topic_card(topic: str, q_total_map: dict, progress_map: dict):
    total_q = int(q_total_map.get(topic, 0))
    attempted = int(progress_map.get(topic, {}).get("total", 0))
    pct_done = _safe_pct(attempted, total_q)

    review_words = get_review_word_count(topic)
    has_review = review_words >= 250
    has_quiz   = total_q >= 5

    review_dot_cls = "dot" + (" green" if has_review else "")
    quiz_dot_cls   = "dot" + (" green" if has_quiz else "")

    # ---- Card container (your .topic-card) ----
    with st.container():
        st.markdown(f"""
        <div class="topic-card">
            <div class="topic-title">{topic}</div>

            <div style="display:flex;align-items:center;gap:.6rem;">
                <div style="flex:1;height:8px;background:#f1f5f9;border-radius:999px;overflow:hidden;">
                    <span style="display:block;height:100%;background:var(--accent);width:{pct_done}%;"></span>
                </div>
                <div style="font-size:.82rem;">{pct_done}%</div>
            </div>

            <div style="display:flex;align-items:center;gap:.5rem;">
                <span class="tiny-btn{' secondary' if not has_review else ''}">
                    <span class="{review_dot_cls}"></span> Review
                </span>
                <span class="tiny-btn{' secondary' if not has_quiz else ''}">
                    <span class="{quiz_dot_cls}"></span> Quiz
                </span>
                <span style="margin-left:auto;font-size:.78rem;color:var(--muted);">
                    Q: {attempted}/{total_q}
                </span>
            </div>

            <div class="topic-actions">
                <button class="tiny-btn" onclick="window.parent.location.hash='rev_{topic}'">Review</button>
                <button class="tiny-btn" onclick="window.parent.location.hash='quiz_{topic}'">Quiz</button>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ---- Hidden Streamlit buttons (triggered by the HTML above) ----
        if st.button("", key=f"rev_{topic}", help="Review", use_container_width=False):
            st.session_state.active_topic = topic
            st.session_state.view = "review"
            st.rerun()
        if st.button("", key=f"quiz_{topic}", help="Quiz", use_container_width=False):
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

def _start_quiz_from_topics(selected_topics: list, n: int):
    df = load_questions_for_subjects(selected_topics)
    df = df.sample(n=min(len(df), int(n)), random_state=42).reset_index(drop=True) if not df.empty else df
    st.session_state.quiz_pool = df
    st.session_state.quiz_idx = 0
    st.session_state.quiz_answers = {}
    st.session_state.quiz_revealed = set()
    st.session_state.quiz_finished = False
    st.session_state.quiz_mode = "normal"
    st.session_state.view = "quiz"
    st.rerun()

# ----------------------------------------------------------------------
# 5. VIEWS (logic unchanged, UI uses your theme classes)
# ----------------------------------------------------------------------
def view_dashboard():
    q_count = questions_count_by_topic()
    prog = load_progress()
    total_q_all = sum(int(q_count.get(t, 0)) for t in q_count)
    attempted_all = sum(int(prog.get(t, {}).get("total", 0)) for t in q_count)
    pct_done = _safe_pct(attempted_all, total_q_all)
    pct_correct = int(round(overall_accuracy() * 100))

    st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div style="border:1px solid var(--border);border-radius:14px;background:var(--card);
                    padding:1rem;box-shadow:0 1px 4px rgba(0,0,0,.03);
                    display:flex;align-items:center;gap:1rem;min-width:260px;">
            <div style="width:80px;height:80px;border-radius:50%;
                        background:conic-gradient(var(--accent) calc({pct_done}*1%), #e5e7eb 0);
                        display:grid;place-items:center;">
                <div style="background:#fff;border-radius:50%;width:54px;height:54px;
                            display:grid;place-items:center;font-weight:700;font-size:1rem;">
                    {pct_done}%
                </div>
            </div>
            <div>
                <div style="font-size:.95rem;font-weight:600;">Completed</div>
                <div style="font-size:.82rem;color:var(--muted);">
                    {attempted_all} of {total_q_all} questions attempted
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div style="border:1px solid var(--border);border-radius:14px;background:var(--card);
                    padding:1rem;box-shadow:0 1px 4px rgba(0,0,0,.03);
                    display:flex;align-items:center;gap:1rem;min-width:260px;">
            <div style="width:80px;height:80px;border-radius:50%;
                        background:conic-gradient(var(--accent) calc({pct_correct}*1%), #e5e7eb 0);
                        display:grid;place-items:center;">
                <div style="background:#fff;border-radius:50%;width:54px;height:54px;
                            display:grid;place-items:center;font-weight:700;font-size:1rem;">
                    {pct_correct}%
                </div>
            </div>
            <div>
                <div style="font-size:.95rem;font-weight:600;">Accuracy</div>
                <div style="font-size:.82rem;color:var(--muted);">
                    Across all attempted questions
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def view_topics():
    st.markdown("<div class='section-title'>Score Topics</div>", unsafe_allow_html=True)
    cats = get_category_map()
    q_count = questions_count_by_topic()
    prog = load_progress()

    s1, s2 = st.columns([2,1])
    with s1:
        q = st.text_input("Search topics", placeholder="Search…", label_visibility="collapsed").strip().lower()
    with s2:
        cat_names = ["All"] + list(cats.keys())
        choose = st.selectbox("Category", cat_names, index=0, label_visibility="collapsed")

    topics = []
    for cat, arr in cats.items():
        if choose != "All" and cat != choose: continue
        for t in arr:
            if q and q not in t.lower(): continue
            topics.append(t)

    if not topics:
        st.info("No topics match your filter.")
        return

    cols = st.columns(3)
    for i, t in enumerate(topics):
        with cols[i % 3]:
            _render_topic_card(t, q_count, prog)

def view_review():
    topic = st.session_state.get("active_topic") or ""
    if not topic:
        st.info("Choose a topic from Score Topics.")
        return
    st.markdown(f"<div class='section-title'>{topic}</div>", unsafe_allow_html=True)
    p = resolve_review_path(topic)
    if not p:
        st.info("No review uploaded yet. Place a `.md` file in `data/reviews/` named with the topic slug.")
        return
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    st.markdown(txt, unsafe_allow_html=True)

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    if st.button("Quiz this topic", use_container_width=True):
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
    if st.button("Start", use_container_width=True):
        if pick and "Any" in pick: pick = []
        _start_quiz_from_topics(pick, int(n))

def view_quiz():
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("No spaced-repetition items due.")
        else:
            st.info("No questions found. Add `.md` files to `data/questions/`.")
        return

    i = st.session_state.get("quiz_idx", 0)
    row = pool.iloc[i]
    pct = int(((i + 1) / len(pool)) * 100)
    st.progress(pct/100)
    suffix = f" • {row.get('subject','')}" if row.get("subject") else ""
    st.caption(f"Question {i+1} of {len(pool)}{suffix}")

    st.markdown(f"<div style='border:1px solid var(--border);background:#fafbfc;border-radius:10px;padding:12px;margin-bottom:6px;'>{row['stem']}</div>", unsafe_allow_html=True)

    letters = ["A","B","C","D","E"]
    prev_choice = st.session_state.quiz_answers.get(row["id"])
    default_idx = letters.index(prev_choice) if prev_choice in letters else 0
    choice = st.radio(
        "", letters, index=default_idx,
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
        verdict_cls = "verdict-ok" if is_correct else "verdict-err"
        verdict_txt = "Correct" if is_correct else "Incorrect"
        st.markdown(f"<span style='font-weight:600;padding:.22rem .6rem;border-radius:999px;display:inline-flex;align-items:center;background:{'#10b9811a' if is_correct else '#ef44441a'};color:{'#065f46' if is_correct else '#7f1d1d'};border:1px solid {'#34d399' if is_correct else '#fca5a5'};'>{verdict_txt}</span>", unsafe_allow_html=True)
        if str(row.get("explanation","")).strip():
            st.markdown(row["explanation"], unsafe_allow_html=True)
        key = f"scored_{row['id']}"
        if not st.session_state.get(key, False):
            record_attempt(row.get("subject",""), row["id"], is_correct)
            if st.session_state.get("quiz_mode") == "spaced":
                sr_update(row["id"], is_correct)
            st.session_state[key] = True

    if st.session_state.quiz_finished:
        idxed = pool.set_index("id")
        scored_ids = [qid for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed]
        correct_n = sum(1 for qid in scored_ids if idxed.loc[qid]["correct"] == st.session_state.quiz_answers[qid])
        denom = len(scored_ids) if scored_ids else len(pool)
        st.success(f"Score: {correct_n}/{denom}")

def render_main():
    view = st.session_state.get("view", "dashboard")
    if view == "topics": view_topics()
    elif view == "review": view_review()
    elif view == "make_quiz": view_make_quiz()
    elif view == "quiz": view_quiz()
    else: view_dashboard()

# ----------------------------------------------------------------------
# 6. LAYOUT – fixed header + animated rail + centred main
# ----------------------------------------------------------------------
rail_w_exp = 0.20
rail_w_col = 0.06
rail_width = rail_w_exp if st.session_state.rail_open else rail_w_col

rail_col, main_col = st.columns([rail_width, 1 - rail_width], gap="small")

# ---- FIXED HEADER (uses your .app-header) ----
st.markdown("""
<div class="app-header">
    <div class="app-header-inner">
        <div class="app-title">PSITE <span style="color:var(--accent);">Mastery</span></div>
        <div></div> <!-- placeholder -->
    </div>
</div>
""", unsafe_allow_html=True)

# ---- LEFT RAIL -------------------------------------------------------
with rail_col:
    st.markdown("<div style='position:sticky;top:0;height:100vh;display:flex;align-items:stretch;'>", unsafe_allow_html=True)
    rail_cls = "edge-rail collapsed" if not st.session_state.rail_open else "edge-rail"
    st.markdown(f"<div class='{rail_cls}' style='width:100%;background:#f9fafb;padding:1rem;display:flex;flex-direction:column;gap:.75rem;transition:width .28s cubic-bezier(.4,0,.2,1),padding .28s cubic-bezier(.4,0,.2,1);'>", unsafe_allow_html=True)

    if not st.session_state.rail_open:
        # three-dot grip
        if st.button("", key="toggle_closed", help="Expand sidebar", use_container_width=False):
            _toggle_rail(); st.rerun()
        st.markdown("""
        <div style="width:36px;height:36px;border-radius:50%;background:#fff;border:1px solid #e5e7eb;
                    box-shadow:0 1px 2px rgba(0,0,0,.06);display:flex;flex-direction:column;
                    align-items:center;justify-content:center;cursor:pointer;">
            <div style="width:4px;height:4px;background:#94a3b8;border-radius:50%;margin:2px 0;"></div>
            <div style="width:4px;height:4px;background:#94a3b8;border-radius:50%;margin:2px 0;"></div>
            <div style="width:4px;height:4px;background:#94a3b8;border-radius:50%;margin:2px 0;"></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        if st.button("", key="toggle_open", help="Collapse sidebar", use_container_width=False):
            _toggle_rail(); st.rerun()
        st.markdown("<div style='font-weight:800;font-size:1.12rem;letter-spacing:.3px;'>PSITE <span style='color:var(--accent);'>Mastery</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:.82rem;color:var(--muted);margin-bottom:.5rem;'>Navigate</div>", unsafe_allow_html=True)

        if st.button("Dashboard", key="nav_dash", use_container_width=True):
            st.session_state.view = "dashboard"; st.rerun()
        if st.button("Score Topics", key="nav_topics", use_container_width=True):
            st.session_state.view = "topics"; st.rerun()
        if st.button("Make Quiz", key="nav_make", use_container_width=True):
            st.session_state.view = "make_quiz"; st.rerun()

        st.markdown("<div style='height:1px;background:var(--border);margin:.75rem 0;'></div>", unsafe_allow_html=True)
        if st.button("Spaced Repetition", key="nav_sr", use_container_width=True):
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

        st.markdown("<div style='height:1px;background:var(--border);margin:.75rem 0;'></div>", unsafe_allow_html=True)
        auth_logout_button()

    st.markdown("</div>", unsafe_allow_html=True)   # /.edge-rail
    st.markdown("</div>", unsafe_allow_html=True)   # /.sticky wrapper

# ---- MAIN CONTENT (centred, scrollable) ----
with main_col:
    st.markdown("<div style='padding:1.5rem 2rem;display:flex;flex-direction:column;gap:1.5rem;align-items:center;'>", unsafe_allow_html=True)
    render_main()
    st.markdown("</div>", unsafe_allow_html=True)
