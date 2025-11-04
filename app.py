# app.py
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components  # for JS toggle

from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, get_topics, resolve_review_path,
    load_questions_for_subjects, load_questions_frame,
    questions_count_by_topic, record_attempt, overall_accuracy,
    sr_due_ids, sr_update, load_progress,
    topic_to_slug, get_review_word_count,  # readiness badges
)

# =============== App shell / theme ===============
st.set_page_config(page_title="PSITE Mastery", page_icon=None,
                   layout="wide", initial_sidebar_state="expanded")
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# --- Styles: keep your dashboard & topics styling intact, add a small header + toggle ---
st.markdown("""
<style>
/* Donut rings for dashboard KPIs (unchanged) */
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

/* Meter + topic bits (unchanged) */
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

/* Minimal custom header with our own sidebar toggle */
.app-header{position:fixed;top:0;left:0;right:0;height:48px;background:#fff;
  border-bottom:1px solid var(--border,#eef0f3);z-index:1000;display:flex;align-items:center;}
.app-header-inner{max-width:1200px;margin:0 auto;width:100%;padding:0 12px;
  display:flex;align-items:center;gap:8px;}
.header-btn{border:1px solid #e5e7eb;background:#fff;border-radius:10px;
  padding:.35rem .6rem;cursor:pointer;font-size:1rem;line-height:1;}
.header-spacer{flex:1;}
/* We keep Streamlit's internal header visible so keyboard/menu still work on mobile,
   but we shrink its footprint. */
header[data-testid="stHeader"] { height: 0 !important; min-height: 0 !important; opacity: 0; }
.block-container{padding-top:calc(48px + 12px)!important;}
.section-title{font-weight:700;margin:.2rem 0 .5rem 0;}
.divider{height:1px;background:var(--border,#eef0f3);margin:1rem 0;}

/* Sidebar brand (so it's never covered) */
.sb-brand{font-weight:900;font-size:1.15rem;letter-spacing:.2px;margin:.2rem 0 1rem 0;}
.sb-brand span{color:var(--accent,#1d4ed8);}
</style>
""", unsafe_allow_html=True)

# ------------------ Header with custom sidebar toggle ------------------
st.markdown("""
<div class="app-header">
  <div class="app-header-inner">
    <button class="header-btn" id="psite-toggle">☰</button>
    <div class="header-spacer"></div>
  </div>
</div>
""", unsafe_allow_html=True)

# Inject JS: simulate Ctrl+B to toggle Streamlit sidebar reliably
components.html("""
<script>
(function(){
  const btn = document.getElementById("psite-toggle");
  if (!btn) return;
  btn.addEventListener("click", function(){
    try{
      const ev = new KeyboardEvent('keydown', {key:'b', ctrlKey:true, bubbles:true});
      document.dispatchEvent(ev);
    }catch(e){}
  });
})();
</script>
""", height=0)

# ------------------ Auth Gate ------------------
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, and quizzes.")
    auth_login_form()
    st.stop()

# ------------------ Sidebar (brand here so it never gets covered) ------------------
with st.sidebar:
    st.markdown("""<div class="sb-brand">PSITE <span>Mastery</span></div>""", unsafe_allow_html=True)

    st.markdown("### Navigate")
    if st.button("Dashboard", use_container_width=True):
        st.session_state.view = "dashboard"; st.rerun()
    if st.button("Score Topics", use_container_width=True):
        st.session_state.view = "topics"; st.rerun()
    if st.button("Make Quiz", use_container_width=True):
        st.session_state.view = "make_quiz"; st.rerun()
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

# ------------------ Utilities (unchanged) ------------------
def _safe_pct(numer: int, denom: int) -> int:
    return int(round(100 * numer / denom)) if denom else 0

def _render_topic_card(topic: str, q_total_map: dict, progress_map: dict):
    """Single visual 'box' with title, progress bar, badges, and buttons INSIDE the box."""
    total_q = int(q_total_map.get(topic, 0))
    attempted = int(progress_map.get(topic, {}).get("total", 0))
    pct_done = _safe_pct(attempted, total_q)

    review_words = get_review_word_count(topic)
    has_review = review_words >= 250
    has_quiz   = total_q >= 5

    review_dot_cls = "dot" + (" green" if has_review else "")
    quiz_dot_cls   = "dot" + (" green" if has_quiz else "")

    with st.container(border=True):
        # Title
        st.markdown(f"<div class='topic-title'>{topic}</div>", unsafe_allow_html=True)
        # Progress row
        prog_cols = st.columns([1, 8, 1])
        with prog_cols[1]:
            st.markdown(f"<div class='meter'><span style='width:{pct_done}%;'></span></div>", unsafe_allow_html=True)
        with prog_cols[2]:
            st.markdown(f"<div style='text-align:right;font-size:.82rem;'>{pct_done}%</div>", unsafe_allow_html=True)
        # Badges line (inside box)
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:.5rem;margin:.35rem 0;'>"
            f"<span class='badge'><span class='{review_dot_cls}'></span>Review</span>"
            f"<span class='badge'><span class='{quiz_dot_cls}'></span>Quiz</span>"
            f"<span class='topic-meta'>Q: {attempted}/{total_q}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
        # Buttons (inside box)
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

# ------------------ Views (unchanged) ------------------
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

    # Top header: category selector & search (unchanged)
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
        _start_quiz_from_topics(pick, int(n))

def view_quiz():
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("✅ No spaced-repetition items due.")
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

# ------------------ Router (unchanged) ------------------
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
