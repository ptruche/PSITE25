# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from psite_core import (
    apply_base_theme, ensure_session_keys, try_auto_login_persisted,
    auth_is_authed, auth_login_form, auth_logout_button,
    get_category_map, get_topics, resolve_review_path,
    load_questions_for_subjects, load_questions_frame,
    questions_count_by_topic, record_attempt, overall_accuracy,
    accuracy_timeseries, topic_strengths, sr_due_ids, sr_update,
    load_progress, load_history,  # using history for avg/day
    debug_scan_report, question_roots,
)

# ------------- Page & base theme -------------
st.set_page_config(
    page_title="PSITE Mastery",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# ------------- Header (fixed, shifted for sidebar) -------------
st.markdown("""
<style>
  :root {
    --sidebar-w: 300px;         /* keep in sync with psite_core sidebar width */
    --header-h: 64px;
    --brand-pad-left: var(--sidebar-w);
  }
  /* Brand header never hides under sidebar */
  .app-header{
    position:fixed; top:0; left:0; right:0; height:var(--header-h);
    background:#fff; border-bottom:1px solid #eef0f3; z-index:1000;
    display:flex; align-items:center;
  }
  .app-header-inner{
    width:100%;
    padding:0 12px;
    display:flex; align-items:center; justify-content:space-between;
    margin-left: var(--brand-pad-left); /* keeps brand clear of sidebar */
  }
  .app-brand .app-title{ font-weight:800; font-size:1.08rem; white-space:nowrap; }
  header{visibility:hidden;height:0!important;}
  .block-container{ padding-top: calc(var(--header-h) + 12px) !important; }

  /* Cleaner chips/pills */
  .chip { display:inline-flex; align-items:center; gap:.4rem;
          padding:.34rem .6rem; border:1px solid #dbe2ea; border-radius:999px;
          background:#fff; cursor:pointer; font-size:.9rem; }
  .chip.active { background:#eef4ff; border-color:#cfe0ff; color:#1d4ed8; }

  /* Topic row list */
  .topic-row-card{
    border:1px solid #eef0f3; border-radius:14px; padding:.75rem .9rem; background:#fff;
    display:flex; align-items:center; gap:1rem; justify-content:space-between;
  }
  .topic-row-main{ display:flex; align-items:center; gap:1rem; flex:1; min-width:0; }
  .topic-row-title{ font-weight:600; font-size:.98rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .meter{ width:160px; height:8px; background:#f2f5fb; border-radius:999px; overflow:hidden; }
  .meter>span{ display:block; height:100%; background:#1d4ed8; width:0%; }

  /* Donut cards */
  .kpi-card { border:1px solid #eef0f3; border-radius:14px; background:#fff; padding:1rem; text-align:center; }
  .kpi-label { font-size:.9rem; color:#6b7280; margin-top:.4rem; }

  /* Buttons minimal */
  .pill{border:1px solid #dbe2ea;border-radius:999px;padding:.28rem .6rem;background:#fff;cursor:pointer;font-size:.85rem;}
  .pill.secondary{background:#f7f9fc;}
  .q-prompt { border:1px solid #eef0f3; background:#fafbfc; border-radius:10px; padding:12px; margin-bottom:6px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
  <div class="app-header-inner">
    <div class="app-brand"><div class="app-title">PSITE Mastery</div></div>
    <div id="logout-slot"></div>
  </div>
</div>
""", unsafe_allow_html=True)

# Put logout in header’s right side
rc = st.columns([1,8,1])[0]
with rc:
    if auth_is_authed():
        auth_logout_button()

# ------------- Login gate -------------
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, Score Topics, and quizzes.")
    auth_login_form()
    st.stop()

# ------------- Sidebar (simplified) -------------
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
    with st.expander("Debug", expanded=False):
        st.caption("Question roots scanned:")
        for r in question_roots():
            st.code(r)
        df_dbg = debug_scan_report()
        if df_dbg.empty:
            st.info("No .md files discovered under the scanned roots.")
        else:
            st.dataframe(df_dbg, use_container_width=True, hide_index=True)

    st.markdown("---")
    auth_logout_button()

# ------------- Helpers -------------
def donut_svg(percent: float, label: str, size: int = 140) -> str:
    """
    Render a clean donut with percentage label using pure SVG (no extra deps).
    """
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
                  stroke-dasharray="{circ:.1f}"
                  stroke-dashoffset="{offset:.1f}"
                  transform="rotate(-90)"></circle>
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
    q_count = questions_count_by_topic()  # dict topic -> total questions
    prog = load_progress()                # dict topic -> {correct, total, ... attempted count}
    total_available = sum(q_count.values())
    total_done = sum(v.get("total", 0) for v in prog.values())
    total_correct = sum(v.get("correct", 0) for v in prog.values())
    return total_available, total_done, total_correct

def _category_chips(active: str | None):
    cats = list(get_category_map().keys())
    # Default to first category if none yet
    if not active or active not in cats:
        active = cats[0] if cats else None
    cols = st.columns(min(5, max(1, len(cats))))
    chosen = active
    for i, c in enumerate(cats):
        with cols[i % len(cols)]:
            cls = "chip active" if c == active else "chip"
            if st.button(c, key=f"cat_{i}", use_container_width=True):
                chosen = c
        st.markdown(f"<div class='{cls}' style='display:none'></div>", unsafe_allow_html=True)
    return chosen

def _render_topic_row(topic: str, q_total_map: dict, progress_map: dict):
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
      <div style="display:flex;gap:.5rem;">
        <form>
          <button class="pill" type="submit" formaction="?view=review&topic={topic}">Review</button>
        </form>
        <form>
          <button class="pill" type="submit" formaction="?view=make_quiz&topic={topic}">Make Quiz</button>
        </form>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ------------- Views -------------
def view_dashboard():
    st.markdown("### Dashboard")

    total_available, total_done, total_correct = _total_available_and_done()
    pct_completed = (100 * total_done / total_available) if total_available else 0.0
    pct_correct = (100 * total_correct / total_done) if total_done else 0.0
    avg_per_day = _avg_per_day_last_7()

    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(donut_svg(pct_completed, "All questions completed"), unsafe_allow_html=True)
    with c2: st.markdown(donut_svg(pct_correct, "Correct among completed"), unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="kpi-card">
          <div style="font-size:2rem;font-weight:800;">{avg}/day</div>
          <div class="kpi-label">7-day average</div>
        </div>
        """.format(avg=f"{avg_per_day:.1f}"), unsafe_allow_html=True)

    # Quick “What to do next”
    st.markdown("---")
    st.markdown("**Next steps**")
    strong, weak = topic_strengths(k=3)
    if weak:
        st.write("• Focus next on your weakest topics:")
        for t, a, n in weak:
            st.write(f"  – {t}: {int(a*100)}% over {n} questions")
    else:
        st.write("• Start a quiz to build performance data.")

def view_topics():
    st.markdown("### Score Topics")

    # Left rail: category selection + search; Right: topic rows of that category
    left, right = st.columns([1,2], gap="large")

    cats = get_category_map()
    q_count = questions_count_by_topic()
    prog = load_progress()

    with left:
        st.caption("Category")
        active_cat = st.session_state.get("active_cat")
        active_cat = _category_chips(active_cat)
        st.session_state.active_cat = active_cat
        st.caption("Search")
        q = st.text_input("Search", placeholder="Search topics", label_visibility="collapsed").strip().lower()

    with right:
        topics = []
        if active_cat and active_cat in cats:
            for t in cats[active_cat]:
                if q and q not in t.lower(): continue
                topics.append(t)

        if not topics:
            st.info("No topics match your filter.")
            return

        # Compact, elegant list
        for t in topics:
            _render_topic_row(t, q_count, prog)
            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

def view_review():
    # Query param support for "Review" click-through
    qp = st.query_params
    topic_from_qp = qp.get("topic", None)
    if topic_from_qp:
        st.session_state.active_topic = topic_from_qp

    topic = st.session_state.get("active_topic") or ""
    if not topic:
        st.info("Choose a topic from Score Topics.")
        return
    st.markdown(f"### {topic}")
    p = resolve_review_path(topic)
    if not p:
        st.info("No review uploaded yet. Place a `.md` file in `data/reviews/` named by topic slug.")
        return
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    st.markdown(txt, unsafe_allow_html=True)

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
    # Query param support for "Make Quiz" click-through
    qp = st.query_params
    pre_topic = qp.get("topic", None)

    st.markdown("### Make a Quiz")
    topics = ["Any"] + get_topics()
    default = [pre_topic] if pre_topic in get_topics() else []
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
            st.info("No questions found. Add `.md` files under the question roots shown in Debug.")
        return

    i = st.session_state.get("quiz_idx", 0)
    row = pool.iloc[i]
    letters = ["A","B","C","D","E"]

    # progress + label
    pct = int(((i + 1) / len(pool)) * 100)
    st.progress(pct/100)
    suffix = f" • {row.get('subject','')}" if row.get("subject") else ""
    st.caption(f"Question {i+1} of {len(pool)}{suffix}")

    # stem
    st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

    # robust previous choice handling
    prev = st.session_state.get("quiz_answers", {}).get(row["id"], None)
    if isinstance(prev, str):
        prev = prev.strip().upper()
    if prev not in letters:
        prev = None
    default_idx = letters.index(prev) if prev in letters else 0

    choice = st.radio(
        label="",
        options=letters,
        index=default_idx,
        format_func=lambda L: row[L],
        label_visibility="collapsed",
        key=f"radio_{row['id']}",
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
        # Log attempt ONCE
        key = f"scored_{row['id']}"
        if not st.session_state.get(key, False):
            record_attempt(row.get("subject",""), row["id"], is_correct)
            if st.session_state.get("quiz_mode") == "spaced":
                sr_update(row["id"], is_correct)
            st.session_state[key] = True

    if st.session_state.quiz_finished:
        # Only count revealed questions in the score denominator
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

# ------------- Router -------------
view = st.session_state.get("view", "dashboard")
# Allow query-param navigation for Review/Make Quiz buttons
qp = st.query_params
if "view" in qp:
    st.session_state.view = qp.get("view")
    # consume the qp (optional)
    # st.query_params.clear()

if st.session_state.view == "topics":
    view_topics()
elif st.session_state.view == "review":
    view_review()
elif st.session_state.view == "make_quiz":
    view_make_quiz()
elif st.session_state.view == "quiz":
    view_quiz()
else:
    view_dashboard()
