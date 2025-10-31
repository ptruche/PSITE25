# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import streamlit.components.v1 as components

from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, get_topics, resolve_review_path,
    load_questions_for_subjects, load_questions_frame,
    questions_count_by_topic, record_attempt,
    sr_due_ids, sr_update, load_progress, load_history,
)

# =================== PAGE SETUP ===================
st.set_page_config(
    page_title="PSITE Mastery",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# =================== HEADER (adaptive to sidebar width) ===================
st.markdown("""
<style>
  :root { --sidebar-w: 300px; --brand-pad-left: var(--sidebar-w); --header-h: 64px; }
  .app-header{
    position:fixed; top:0; left:0; right:0; height:var(--header-h);
    background:#fff; border-bottom:1px solid #eef0f3; z-index:1000;
    display:flex; align-items:center;
  }
  .app-header-inner{
    width:100%; padding:0 12px; display:flex; align-items:center; justify-content:flex-start;
    margin-left: var(--brand-pad-left); transition: margin-left .18s ease;
  }
  .app-brand .app-title{ font-weight:800; font-size:1.08rem; white-space:nowrap; }
  header{visibility:hidden;height:0!important;}
  .block-container{ padding-top: calc(var(--header-h) + 12px) !important; }

  .chipbar { display:flex; gap:.5rem; flex-wrap:wrap; align-items:center; margin:.25rem 0 .75rem 0; }
  .chip { display:inline-flex; align-items:center; gap:.4rem; padding:.34rem .6rem; border:1px solid #dbe2ea; border-radius:999px; background:#fff; cursor:pointer; font-size:.9rem; white-space: nowrap; }
  .chip.active { background:#eef4ff; border-color:#cfe0ff; color:#1d4ed8; }

  .topic-row-card{ border:1px solid #eef0f3; border-radius:14px; padding:.75rem .9rem; background:#fff; display:flex; align-items:center; gap:1rem; justify-content:space-between; }
  .topic-row-main{ display:flex; align-items:center; gap:1rem; flex:1; min-width:0; }
  .topic-row-title{ font-weight:600; font-size:.98rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .meter{ width:200px; height:8px; background:#f2f5fb; border-radius:999px; overflow:hidden; }
  .meter>span{ display:block; height:100%; background:#1d4ed8; width:0%; }

  .kpi-card { border:1px solid #eef0f3; border-radius:14px; background:#fff; padding:1rem; text-align:center; }
  .kpi-label { font-size:.9rem; color:#6b7280; margin-top:.4rem; }

  .pill{border:1px solid #dbe2ea;border-radius:999px;padding:.28rem .6rem;background:#fff;cursor:pointer;font-size:.85rem;}
  .pill.secondary{background:#f7f9fc;}
  .q-prompt { border:1px solid #eef0f3; background:#fafbfc; border-radius:10px; padding:12px; margin-bottom:6px; }
</style>

<div class="app-header">
  <div class="app-header-inner">
    <div class="app-brand"><div class="app-title">PSITE Mastery</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

def _watch_sidebar_width():
    components.html("""
    <script>
      (function(){
        function setPad(px){
          try { document.documentElement.style.setProperty('--brand-pad-left', px + 'px'); } catch(e){}
        }
        function readSidebarWidth(){
          const sb = parent.document.querySelector('[data-testid="stSidebar"]');
          if (!sb) { setPad(0); return; }
          const rect = sb.getBoundingClientRect();
          setPad(rect.width || 0);
        }
        readSidebarWidth();
        const sb = parent.document.querySelector('[data-testid="stSidebar"]');
        if (sb && 'ResizeObserver' in window) {
          const ro = new ResizeObserver(()=>readSidebarWidth()); ro.observe(sb);
        }
        window.addEventListener('resize', readSidebarWidth);
        let ticks = 0;
        const id = setInterval(()=>{ readSidebarWidth(); if (++ticks > 40) clearInterval(id); }, 250);
      })();
    </script>
    """, height=0)

_watch_sidebar_width()

# =================== AUTH GATE ===================
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, Score Topics, and quizzes.")
    auth_login_form()
    st.stop()

# =================== SIDEBAR ===================
with st.sidebar:
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

# =================== HELPERS ===================
def donut_svg(percent: float, label: str, size: int = 140) -> str:
    pct = max(0, min(100, int(round(percent))))
    r = 52
    cx = cy = size // 2
    circ = 2 * 3.14159265 * r
    offset = circ * (1 - pct / 100.0)
    return f"""
    <div class="kpi-card">
      <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="display:block;margin:0 auto;">
        <g transform="translate({cx},{cy})">
          <circle r="{r}" fill="none" stroke="#f1f5f9" stroke-width="12"></circle>
          <circle r="{r}" fill="none" stroke="#1d4ed8" stroke-width="12"
                  stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}" transform="rotate(-90)"></circle>
          <text text-anchor="middle" dominant-baseline="central" font-size="20" font-weight="700">{pct}%</text>
        </g>
      </svg>
      <div class="kpi-label">{label}</div>
    </div>
    """

def _avg_per_day_last_7() -> float:
    hist = load_history()
    if not hist: return 0.0
    since = datetime.utcnow() - timedelta(days=7)
    n = sum(1 for h in hist if datetime.utcfromtimestamp(h.get("ts", 0)) >= since)
    return round(n / 7.0, 1)

def _total_available_and_done():
    q_count = questions_count_by_topic()
    prog = load_progress()
    total_available = sum(q_count.values())
    total_done = sum(v.get("total", 0) for v in prog.values())
    total_correct = sum(v.get("correct", 0) for v in prog.values())
    return total_available, total_done, total_correct

def _render_topic_row(topic: str, q_total_map: dict, progress_map: dict):
    """Pure Streamlit controls (no hard navigation) to avoid auth loss."""
    total_q = q_total_map.get(topic, 0)
    attempted = progress_map.get(topic, {}).get("total", 0)
    pct_done = int(100 * attempted / total_q) if total_q else 0

    st.markdown(f"""
    <div class="topic-row-card">
      <div class="topic-row-main">
        <div class="topic-row-title">{topic}</div>
        <div class="meter"><span style="width:{pct_done}%"></span></div>
        <div style="min-width:48px;text-align:right;font-size:.85rem;">{pct_done}%</div>
      </div>
      <div id="btn-slot-{topic}"></div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("Review", key=f"rev_{topic}", use_container_width=True):
            st.session_state.active_topic = topic
            st.session_state.view = "review"
            st.rerun()
    with c2:
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

def _category_chipbar_top(active: str | None):
    cats = list(get_category_map().keys())
    if not cats: return None
    if not active or active not in cats: active = cats[0]
    st.markdown("<div class='chipbar'>", unsafe_allow_html=True)
    cols = st.columns(min(6, max(1, len(cats))))
    chosen = active
    for i, c in enumerate(cats):
        with cols[i % len(cols)]:
            clicked = st.button(c, key=f"cat_{i}", use_container_width=True)
            if clicked: chosen = c
    st.markdown("</div>", unsafe_allow_html=True)
    return chosen

# =================== VIEWS ===================
def view_dashboard():
    st.markdown("### Dashboard")
    total_available, total_done, total_correct = _total_available_and_done()
    pct_completed = (100 * total_done / total_available) if total_available else 0.0
    pct_correct = (100 * total_correct / total_done) if total_done else 0.0
    avg_per_day = _avg_per_day_last_7()
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(donut_svg(pct_completed, "Completed"), unsafe_allow_html=True)
    with c2: st.markdown(donut_svg(pct_correct, "Correct"), unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card">
          <div style="font-size:2rem;font-weight:800;">{avg_per_day:.1f}/day</div>
          <div class="kpi-label">7-day average</div>
        </div>
        """, unsafe_allow_html=True)

def view_topics():
    st.markdown("### Score Topics")
    cats = get_category_map()
    q_count = questions_count_by_topic()
    prog = load_progress()

    active_cat = st.session_state.get("active_cat")
    active_cat = _category_chipbar_top(active_cat)
    st.session_state.active_cat = active_cat

    q = st.text_input("Search topics", placeholder="Search…").strip().lower()
    topics = []
    if active_cat and active_cat in cats:
        for t in cats[active_cat]:
            if q and q not in t.lower(): continue
            topics.append(t)

    if not topics:
        st.info("No topics match your filter.")
        return

    for t in topics:
        _render_topic_row(t, q_count, prog)
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

def view_review():
    # No query-param navigation needed; relies on session_state
    topic = st.session_state.get("active_topic") or ""
    if not topic:
        st.info("Choose a topic from Score Topics.")
        return
    st.markdown(f"### {topic}")
    p = resolve_review_path(topic)
    if not p:
        st.info("No review uploaded yet. Place a `.md` file in `data/reviews/`.")
        return
    with open(p, "r", encoding="utf-8") as f:
        st.markdown(f.read(), unsafe_allow_html=True)
    st.markdown("---")
    if st.button("Quiz this topic ▶"):
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
    st.markdown("### Make a Quiz")
    pre = st.session_state.get("active_topic")
    topics = ["Any"] + get_topics()
    default = [pre] if pre in get_topics() else []
    pick = st.multiselect("Choose topics (or leave empty for Any):", topics, default=default)
    n = st.number_input("Number of questions", 5, 100, 20, step=5)
    if st.button("Start ▶", use_container_width=True):
        if pick and "Any" in pick: pick = []
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

def view_quiz():
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("✅ No spaced-repetition items due.")
        else:
            st.info("No questions found. Add `.md` files under data/questions/<topic>/")
        return

    i = st.session_state.get("quiz_idx", 0)
    row = pool.iloc[i]
    letters = ["A","B","C","D","E"]

    pct = int(((i + 1) / len(pool)) * 100)
    st.progress(pct/100)
    suffix = f" • {row.get('subject','')}" if row.get("subject") else ""
    st.caption(f"Question {i+1} of {len(pool)}{suffix}")

    st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

    prev = st.session_state.get("quiz_answers", {}).get(row["id"], None)
    if isinstance(prev, str): prev = prev.strip().upper()
    default_idx = letters.index(prev) if prev in letters else 0

    choice = st.radio(
        "", letters, index=default_idx,
        format_func=lambda L: row[L],
        label_visibility="collapsed",
        key=f"radio_{row['id']}"
    )
    st.session_state.quiz_answers[row["id"]] = str(choice).strip().upper()

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
        is_correct = (st.session_state.quiz_answers.get(row["id"]) == row["correct"])
        verdict_class = "pill" + ("" if is_correct else " pill secondary")
        verdict_text = "Correct" if is_correct else "Incorrect"
        st.markdown(f"<span class='{verdict_class}'>{verdict_text}</span>", unsafe_allow_html=True)
        exp = (row.get("explanation") or "").strip()
        if exp:
            st.markdown(exp, unsafe_allow_html=True)

        key = f"scored_{row['id']}"
        if not st.session_state.get(key, False):
            record_attempt(row.get("subject",""), row["id"], is_correct)
            if st.session_state.get("quiz_mode") == "spaced":
                sr_update(row["id"], is_correct)
            st.session_state[key] = True

    if st.session_state.quiz_finished:
        revealed_ids = set(st.session_state.quiz_revealed)
        if not revealed_ids:
            st.info("Reveal answers to compute a score.")
            return
        correct_map = pool.set_index("id")["correct"].to_dict()
        correct_n = sum(
            1 for qid, ans in st.session_state.quiz_answers.items()
            if qid in revealed_ids and correct_map.get(qid) == ans
        )
        st.success(f"Score: {correct_n}/{len(revealed_ids)}")

# =================== ROUTER ===================
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
