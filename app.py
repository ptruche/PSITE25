# app.py
import streamlit as st
import pandas as pd

# ----------------------------------------------------------------------
# 1. IMPORT CORE + LOAD theme.css
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

# Load your exact theme.css
with open("theme.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

apply_base_theme()   # keep any JS from core

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
    st.session_state.rail_open = True

def _toggle_rail():
    st.session_state.rail_open = not st.session_state.rail_open

def _safe_pct(numer: int, denom: int) -> int:
    return int(round(100 * numer / denom)) if denom else 0

# ----------------------------------------------------------------------
# 4. TOPIC CARD (uses your .topic-card, .tiny-btn)
# ----------------------------------------------------------------------
def _render_topic_card(topic: str, q_total_map: dict, progress_map: dict):
    total_q = int(q_total_map.get(topic, 0))
    attempted = int(progress_map.get(topic, {}).get("total", 0))
    pct_done = _safe_pct(attempted, total_q)

    review_words = get_review_word_count(topic)
    has_review = review_words >= 250
    has_quiz   = total_q >= 5

    review_cls = "tiny-btn secondary" if not has_review else "tiny-btn"
    quiz_cls   = "tiny-btn secondary" if not has_quiz else "tiny-btn"

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

            <div style="display:flex;align-items:center;gap:.5rem;font-size:.78rem;color:var(--muted);">
                <span class="{review_cls}">Review</span>
                <span class="{quiz_cls}">Quiz</span>
                <span style="margin-left:auto;">Q: {attempted}/{total_q}</span>
            </div>

            <div class="topic-actions">
                <button class="tiny-btn" onclick="window.location.hash='rev_{topic}'">Review</button>
                <button class="tiny-btn" onclick="window.location.hash='quiz_{topic}'">Quiz</button>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("", key=f"rev_{topic}"):
            st.session_state.active_topic = topic
            st.session_state.view = "review"
            st.rerun()
        if st.button("", key=f"quiz_{topic}"):
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
# 5. VIEWS (uses your theme classes)
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
                    {attempted_all} of {total_q_all} questions
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
                    Across all attempts
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ... (view_topics, view_review, view_make_quiz, view_quiz, render_main – same as before) ...
# (Full code below – only changed layout part)

# ----------------------------------------------------------------------
# 6. LAYOUT – fixed header + sticky rail + centered main
# ----------------------------------------------------------------------
rail_w_exp = 0.20
rail_w_col = 0.06
rail_width = rail_w_exp if st.session_state.rail_open else rail_w_col

rail_col, main_col = st.columns([rail_width, 1 - rail_width], gap="small")

# ---- FIXED HEADER (your .app-header) ----
st.markdown(f"""
<div class="app-header">
    <div class="app-header-inner">
        <div class="app-title">PSITE <span style="color:var(--accent);">Mastery</span></div>
        <div>{auth_logout_button() if st.session_state.get("auth_user") else ""}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---- STICKY RAIL (starts at top, full height) ----
with rail_col:
    st.markdown("""
    <div style="position:sticky;top:0;height:100vh;display:flex;align-items:stretch;">
        <div id="rail" style="width:100%;background:#f9fafb;padding:1rem 1rem;
                            display:flex;flex-direction:column;gap:.75rem;
                            transition:width .28s cubic-bezier(.4,0,.2,1),padding .28s cubic-bezier(.4,0,.2,1);">
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Use JS to toggle class
    if st.button("", key="toggle_rail", help="Toggle sidebar"):
        _toggle_rail()
        st.rerun()

    # Render content based on state
    rail = st.session_state.rail_open
    cls = "" if rail else "collapsed"
    st.markdown(f"<div class='{cls}' style='width:100%;'>", unsafe_allow_html=True)

    if not rail:
        # three-dot grip
        st.markdown("""
        <div style="width:36px;height:36px;border-radius:50%;background:#fff;
                    border:1px solid #e5e7eb;box-shadow:0 1px 2px rgba(0,0,0,.06);
                    display:flex;flex-direction:column;align-items:center;justify-content:center;
                    cursor:pointer;" onclick="document.getElementById('toggle_rail').click();">
            <div style="width:4px;height:4px;background:#94a3b8;border-radius:50%;margin:2px 0;"></div>
            <div style="width:4px;height:4px;background:#94a3b8;border-radius:50%;margin:2px 0;"></div>
            <div style="width:4px;height:4px;background:#94a3b8;border-radius:50%;margin:2px 0;"></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='font-size:.82rem;color:var(--muted);'>Navigate</div>", unsafe_allow_html=True)
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

    st.markdown("</div>", unsafe_allow_html=True)

# ---- MAIN CONTENT (centered) ----
with main_col:
    st.markdown("""
    <div style="padding:1.5rem 2rem;display:flex;flex-direction:column;
                gap:1.5rem;align-items:center;">
    """, unsafe_allow_html=True)
    render_main()
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 7. JS TO TOGGLE RAIL CLASS
# ----------------------------------------------------------------------
st.markdown(f"""
<script>
    const rail = document.getElementById('rail');
    {'rail.classList.add("collapsed");' if not st.session_state.rail_open else ''}
</script>
""", unsafe_allow_html=True)
