# app.py
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, get_topics, resolve_review_path,
    load_questions_for_subjects, load_questions_frame,
    questions_count_by_topic, record_attempt, overall_accuracy,
    sr_due_ids, sr_update, load_progress,
    topic_to_slug, get_review_word_count,
)

# ---------------- App shell / theme ----------------
st.set_page_config(page_title="PSITE Mastery", page_icon=None,
                   layout="wide", initial_sidebar_state="expanded")
apply_base_theme()

st.markdown("""
<style>
/* Hard reset top spacing across Streamlit containers */
html, body { margin:0 !important; padding:0 !important; }
[data-testid="stAppViewContainer"] { padding-top:0 !important; }
main.block-container { padding-top:0 !important; margin-top:0 !important; }
main .block-container > div:first-child { margin-top:0 !important; }

/* Hide the default header/toolbar gaps completely */
header[data-testid="stHeader"] { height:0 !important; min-height:0 !important; padding:0 !important; margin:0 !important; opacity:0 !important; }
div[data-testid="stToolbar"] { display:none !important; }

/* Ensure our rail wrapper really starts at the top */
.edge-rail-wrap { position: sticky; top: 0; height: 100vh; }

/* Make the whole main area start flush at top and be the scroller */
.main-scroll { height: 100vh; overflow: auto; padding-top: 0 !important; margin-top: 0 !important; }

/* (Optional) Remove any mysterious extra spacers some themes add */
.block-container div:empty { display: none !important; }
</style>
""", unsafe_allow_html=True)


ensure_session_keys()
try_auto_login_persisted()

# ---------------- Styles (dashboard/topics unchanged) ----------------
st.markdown("""
<style>
/* Remove default header gap */
header[data-testid="stHeader"] { height:0 !important; min-height:0 !important; opacity:0 !important; }
.block-container{ padding-top:0 !important; }

/* ===== Edge Rail (anchored, top-aligned, smooth) ===== */
.layout-root{ display:flex; gap:0; width:100%; }
.edge-rail-col{ position:relative; }
.edge-rail-wrap{
  position:sticky; top:0; height:100vh; /* anchor to top, full height */
  display:flex; align-items:stretch;
}
.edge-rail{
  width:100%; height:100%; overflow:hidden; /* rail itself doesn't scroll */
  background:#f5f7fb;
  border-right:1px solid #e7ecf3;
  padding:12px 12px;
  border-radius:0 12px 12px 0;
  box-shadow:1px 0 0 rgba(0,0,0,.02) inset;
  display:flex; flex-direction:column; gap:8px; justify-content:flex-start;
  transition: padding .22s ease, background .22s ease, border-color .22s ease;
}
.edge-rail.collapsed{
  padding:10px 8px; align-items:center; justify-content:center;
}

/* Rail content */
.edge-rail-title{font-weight:900;font-size:1.05rem;letter-spacing:.2px;margin:.25rem 0 .2rem 0;}
.edge-rail-sub{color:#6b7280;font-size:.82rem;margin:.1rem 0 .4rem 0;}
.edge-rail .nav-btn{
  width:100%; border-radius:10px; padding:.48rem .65rem;
  border:1px solid #e5e7eb; background:#fff; margin-bottom:.45rem;
}
.edge-rail .sep{height:1px;background:#e9edf5;margin:.55rem 0;}

/* Main area should scroll independently while rail stays put */
.main-scroll{
  height:100vh; overflow:auto; padding:12px 16px 24px;
}

/* Dashboard donuts */
.kpi-wrap{display:flex;gap:24px;flex-wrap:wrap;}
.kpi-card{border:1px solid var(--border,#eef0f3);border-radius:16px;background:#fff;
  padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.04);display:flex;align-items:center;gap:16px;}
.kpi-ring{width:84px;height:84px;border-radius:50%;
  background:conic-gradient(var(--accent,#1d4ed8) calc(var(--val,0)*1%), #e9eef8 0);
  display:grid;place-items:center;}
.kpi-ring > div{background:#fff;border-radius:50%;width:58px;height:58px;display:grid;place-items:center;
  font-weight:700;font-size:1rem;color:#111;border:1px solid #f0f3f8;}
.kpi-meta{display:flex;flex-direction:column;gap:2px;}
.kpi-label{font-size:.92rem;color:#374151;font-weight:600;}
.kpi-sub{font-size:.82rem;color:#6b7280}

/* Topic cards (unchanged visuals) */
.meter{flex:1;height:8px;background:#f2f5fb;border-radius:999px;overflow:hidden;}
.meter>span{display:block;height:100%;background:var(--accent,#1d4ed8);width:0%;}
.dot{width:9px;height:9px;border-radius:50%;background:#d1d5db;display:inline-block;margin-right:6px;
  border:1px solid #cbd5e1;transform:translateY(1px);}
.dot.green{background:#22c55e;border-color:#22c55e;}
.badge{display:inline-flex;align-items:center;gap:6px;padding:.18rem .5rem;border:1px solid #e5e7eb;
  border-radius:999px;font-size:.78rem;color:#374151;background:#fff;}
.topic-title{font-weight:600;font-size:.98rem;line-height:1.2;margin-bottom:.25rem;}
.topic-row{display:flex;align-items:center;gap:.6rem;margin:.25rem 0 .35rem 0;}
.topic-meta{font-size:.78rem;color:#6b7280}
.q-prompt{border:1px solid var(--border,#eef0f3);background:#fafbfc;border-radius:10px;padding:12px;margin-bottom:6px;}
.verdict{font-weight:600;padding:.22rem .6rem;border-radius:999px;border:1px solid transparent;display:inline-flex;align-items:center;}
.verdict-ok{background:#10b9811a;color:#065f46;border-color:#34d399;}
.verdict-err{background:#ef44441a;color:#7f1d1d;border-color:#fca5a5;}

/* Sections */
.section-title{font-weight:700;margin:.2rem 0 .5rem 0;}
.divider{height:1px;background:#eef0f3;margin:1rem 0;}

/* ----- NEW: tiny tab on the right edge of the rail ----- */
button[data-testid="stButton"][key="rail_tab"] {
    position: absolute !important;
    right: -12px; top: 50%; transform: translateY(-50%);
    width: 24px !important; height: 48px !important;
    background: #fff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 0 8px 8px 0 !important;
    box-shadow: 2px 0 4px rgba(0,0,0,.07) !important;
    font-size: 14px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 10;
    cursor: pointer;
}
button[data-testid="stButton"][key="rail_tab"]:hover {
    background: #f8fafc !important;
    border-color: #cbd5e1 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------- Auth gate ----------------
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, and quizzes.")
    auth_login_form()
    st.stop()

# ---------------- Rail state ----------------
if "rail_open" not in st.session_state:
    st.session_state.rail_open = True # expanded by default

def _toggle_rail():
    st.session_state.rail_open = not st.session_state.rail_open

def _safe_pct(numer: int, denom: int) -> int:
    return int(round(100 * numer / denom)) if denom else 0

# ---------------- Topic card renderer (unchanged visuals) ----------------
def _render_topic_card(topic: str, q_total_map: dict, progress_map: dict):
    total_q = int(q_total_map.get(topic, 0))
    attempted = int(progress_map.get(topic, {}).get("total", 0))
    pct_done = _safe_pct(attempted, total_q)

    review_words = get_review_word_count(topic)
    has_review = review_words >= 250
    has_quiz = total_q >= 5

    review_dot_cls = "dot" + (" green" if has_review else "")
    quiz_dot_cls = "dot" + (" green" if has_quiz else "")

    with st.container(border=True):
        st.markdown(f"<div class='topic-title'>{topic}</div>", unsafe_allow_html=True)
        prog_cols = st.columns([1, 8, 1])
        with prog_cols[1]:
            st.markdown(f"<div class='meter'><span style='width:{pct_done}%;'></span></div>", unsafe_allow_html=True)
        with prog_cols[2]:
            st.markdown(f"<div style='text-align:right;font-size:.82rem;'>{pct_done}%</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:.5rem;margin:.35rem 0;'>"
            f"<span class='badge'><span class='{review_dot_cls}'></span>Review</span>"
            f"<span class='badge'><span class='{quiz_dot_cls}'></span>Quiz</span>"
            f"<span class='topic-meta'>Q: {attempted}/{total_q}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Review", key=f"rev_{topic}", use_container_width=True):
                st.session_state.active_topic = topic
                st.session_state.view = "review"
                st.rerun()
        with b2:
            if st.button("Quiz", key=f"quiz_{topic}", use_container_width=True):
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

# ---------------- Views (your preferred visuals kept) ----------------
def view_dashboard():
    q_count = questions_count_by_topic()
    prog = load_progress()
    total_q_all = sum(int(q_count.get(t, 0)) for t in q_count.keys())
    attempted_all = sum(int(prog.get(t, {}).get("total", 0)) for t in q_count.keys())
    pct_done = _safe_pct(attempted_all, total_q_all)
    pct_correct = int(round(overall_accuracy() * 100))

    st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-ring" style="--val:{pct_done};">
            <div>{pct_done}%</div>
          </div>
          <div class="kpi-meta">
            <div class="kpi-label">Completed</div>
            <div class="kpi-sub">{attempted_all} of {total_q_all} questions attempted</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-ring" style="--val:{pct_correct};">
            <div>{pct_correct}%</div>
          </div>
          <div class="kpi-meta">
            <div class="kpi-label">Accuracy</div>
            <div class="kpi-sub">Across all attempted questions</div>
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
        if choose != "All" and cat != choose:
            continue
        for t in arr:
            if q and q not in t.lower():
                continue
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
        if pick and "Any" in pick:
            pick = []
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

# ---------------- Router ----------------
def render_main():
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

# ---------------- Layout: anchored rail + independent main scroll ----------------
rail_w_expanded = 0.18
rail_w_collapsed = 0.06
rail_w = rail_w_expanded if st.session_state.rail_open else rail_w_collapsed
main_w = 1.0 - rail_w

rail_col, main_col = st.columns([rail_w, main_w], gap="small")

# ---------- RAIL ----------
with rail_col:
    st.markdown("<div class='edge-rail-wrap'>", unsafe_allow_html=True)

    rail_cls = "edge-rail collapsed" if not st.session_state.rail_open else "edge-rail"
    st.markdown(f"<div class='{rail_cls}'>", unsafe_allow_html=True)

    # ---- tiny tab on the right edge ----
    tab_icon = "Left Arrow" if st.session_state.rail_open else "Right Arrow"
    if st.button(
        tab_icon,
        key="rail_tab",
        help="Collapse / Expand sidebar",
        use_container_width=False,
    ):
        _toggle_rail()
        st.rerun()

    # ---- content (only when expanded) ----
    if st.session_state.rail_open:
        st.markdown("<div class='edge-rail-title'>PSITE <span style='color:#1d4ed8'>Mastery</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='edge-rail-sub'>Navigate</div>", unsafe_allow_html=True)

        if st.button("Dashboard", key="nav_dash", use_container_width=True):
            st.session_state.view = "dashboard"; st.rerun()
        if st.button("Score Topics", key="nav_topics", use_container_width=True):
            st.session_state.view = "topics"; st.rerun()
        if st.button("Make Quiz", key="nav_make", use_container_width=True):
            st.session_state.view = "make_quiz"; st.rerun()

        st.markdown("<div class='sep'></div>", unsafe_allow_html=True)
        if st.button("Spaced Repetition Right Arrow", key="nav_sr", use_container_width=True):
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

        st.markdown("<div class='sep'></div>", unsafe_allow_html=True)
        auth_logout_button()

    st.markdown("</div>", unsafe_allow_html=True)  # /.edge-rail
    st.markdown("</div>", unsafe_allow_html=True)  # /.edge-rail-wrap

# ---------- MAIN ----------
with main_col:
    st.markdown("<div class='main-scroll'>", unsafe_allow_html=True)
    render_main()
    st.markdown("</div>", unsafe_allow_html=True)
