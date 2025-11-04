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
    accuracy_timeseries, topic_strengths, sr_due_ids, sr_update,
    load_progress, topic_to_slug, slug_to_topic, get_review_word_count,
)

st.set_page_config(
    page_title="PSITE Mastery",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# ---------- tiny CSS override to keep your previous spacing/arrangement ----------
st.markdown("""
<style>
/* Ensure content expands when sidebar is collapsed (default Streamlit behavior),
   but tighten card grid spacing to the previous feel. */
.block-container { padding-top: 10px !important; }

/* Topic grid feel you liked */
.topics-grid { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; }

/* Keep topic cards compact and tidy as before */
.topic-card{
  border:1px solid var(--border); border-radius:14px; background:#fff; padding:.75rem;
  box-shadow:0 1px 4px rgba(0,0,0,.03); display:flex; gap:.55rem; flex-direction:column;
}
.topic-title{ font-weight:600; font-size:.98rem; line-height:1.2; }
.topic-row{ display:flex; align-items:center; gap:.6rem; }
.meter{ flex:1; height:8px; background:#f2f5fb; border-radius:999px; overflow:hidden; }
.meter>span{ display:block; height:100%; background:var(--accent); width:0%; }

/* Actions are INSIDE the card */
.topic-actions{ display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; margin-top: .2rem; }
.btn{ display:inline-flex; align-items:center; gap:.4rem; border:1px solid #dbe2ea; border-radius:999px;
      padding:.28rem .66rem; background:#fff; cursor:pointer; font-size:.85rem; text-decoration:none; }
.btn.sm{ font-size:.82rem; padding:.22rem .58rem; }
.btn.green{ background:#e8f6ef; border-color:#b8e4cc; }
.topic-meta{ font-size:.8rem; color:#6b7280; margin-left:auto; }

/* Circle stats (minimal dashboard) */
.circle-stat{ display:flex; flex-direction:column; align-items:center; gap:.4rem; }
.circle{
  --val: 0.0;
  width:120px; height:120px; border-radius:50%;
  background:
    radial-gradient(closest-side, #fff 78%, transparent 80% 100%),
    conic-gradient(var(--accent) calc(var(--val)*1turn), #eef2f9 0);
  display:flex; align-items:center; justify-content:center;
  font-weight:800; font-size:1.15rem; color:#111;
  border:1px solid var(--border);
}
.circle > span{ transform: translateY(-1px); }
.circle + .label{ font-size:.9rem; color:#374151 }

/* Category selector row at the top of the Score Topics page */
.cat-row{ display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom:.4rem; }
.cat-pill{
  padding:.26rem .6rem; border:1px solid #dbe2ea; border-radius:999px; background:#fff; font-size:.85rem;
  cursor:pointer; text-decoration:none; color:#111;
}
.cat-pill.active{ background:#e8f0ff; border-color:#c9d7ff; color:#113; font-weight:600; }

/* Brand in sidebar (from psite_core theme); no fixed header */
.sb-brand { font-weight:900; font-size:1.15rem; letter-spacing:.2px; margin:.2rem 0 1rem 0; }
.sb-brand span{ color: var(--accent); }
.section-title{ font-weight:700; margin:.2rem 0 .6rem 0; }
.divider{height:1px;background:var(--border);margin:1rem 0;}
.q-prompt { border:1px solid var(--border); background:#fafbfc; border-radius:10px; padding:12px; margin-bottom:6px; }
.verdict { font-weight:600; padding:.22rem .6rem; border-radius:999px; border:1px solid transparent; display:inline-flex; align-items:center; }
.verdict-ok  { background:#10b9811a; color:#065f46; border-color:#34d399; }
.verdict-err { background:#ef44441a; color:#7f1d1d; border-color:#fca5a5; }
</style>
<script>
  // Set progress values for circle stats (reads data-value attribute)
  for (const el of window.parent.document.querySelectorAll('.circle')) {
    const v = parseFloat(el.getAttribute('data-value') || '0');
    el.style.setProperty('--val', isFinite(v) ? v : 0);
  }
</script>
""", unsafe_allow_html=True)

# ------------------ Auth Gate ------------------
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, and quizzes.")
    auth_login_form()
    st.stop()

# ------------------ Router via query params for HTML buttons ------------------
def _consume_action_query():
    qp = dict(st.query_params)
    action = qp.get("action")
    slug = qp.get("topic")
    if action and slug:
        topic = slug_to_topic(slug)
        st.query_params.clear()  # prevent loops
        if not topic:
            return
        if action == "review":
            st.session_state.active_topic = topic
            st.session_state.view = "review"
            st.rerun()
        elif action == "quiz":
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

_consume_action_query()

# ------------------ Sidebar ------------------
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

# ------------------ Utilities ------------------
def _render_topic_card(topic: str, q_total_map: dict, progress_map: dict):
    total_q = int(q_total_map.get(topic, 0))
    attempted = int(progress_map.get(topic, {}).get("total", 0))
    pct_done = int(100 * attempted / total_q) if total_q else 0

    review_words = get_review_word_count(topic)
    has_review = review_words >= 250
    has_quiz   = total_q >= 5

    review_cls = "btn sm" + (" green" if has_review else "")
    quiz_cls   = "btn sm" + (" green" if has_quiz else "")

    slug = topic_to_slug(topic)
    st.markdown(f"""
    <div class="topic-card">
      <div class="topic-title">{topic}</div>
      <div class="topic-row">
        <div class="meter"><span style="width:{pct_done}%"></span></div>
        <div style="width:42px;text-align:right;font-size:.82rem;">{pct_done}%</div>
      </div>
      <div class="topic-actions">
        <a class="{review_cls}" href="?action=review&topic={slug}">Review</a>
        <a class="{quiz_cls}" href="?action=quiz&topic={slug}">Quiz</a>
        <span class="topic-meta">Q: {attempted}/{total_q}{' • Review ready' if has_review else ''}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

def _start_quiz_from_topics(selected_topics: list, n: int):
    df = load_questions_for_subjects(selected_topics)
    if not df.empty:
        df = df.sample(n=min(len(df), int(n)), random_state=42).reset_index(drop=True)
    st.session_state.quiz_pool = df
    st.session_state.quiz_idx = 0
    st.session_state.quiz_answers = {}
    st.session_state.quiz_revealed = set()
    st.session_state.quiz_finished = False
    st.session_state.quiz_mode = "normal"
    st.session_state.view = "quiz"
    st.rerun()

# ------------------ Views ------------------
def view_dashboard():
    st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)

    # Accuracy (0..1)
    acc = overall_accuracy()

    # Completion = attempted / total available
    q_count = questions_count_by_topic()
    total_available = sum(q_count.values())
    prog = load_progress()
    total_attempted = sum(v.get("total", 0) for v in prog.values())
    completion = (total_attempted / total_available) if total_available else 0.0

    # Daily average (30 days)
    series = accuracy_timeseries(days=30)
    attempts_last_30 = sum(n for _, _, n in series) if series else 0
    daily_avg = attempts_last_30 / 30 if attempts_last_30 else 0

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        st.markdown(f"""
        <div class="circle-stat">
          <div class="circle" data-value="{completion:.2f}"><span>{int(round(completion*100))}%</span></div>
          <div class="label">Completed</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="circle-stat">
          <div class="circle" data-value="{acc:.2f}"><span>{int(round(acc*100))}%</span></div>
          <div class="label">Correct</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.metric("Avg questions/day (30d)", f"{daily_avg:.1f}")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    strong, weak = topic_strengths(k=5)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Strongest topics**")
        if not strong: st.caption("—")
        for t, a, n in strong:
            st.write(f"{t} — {int(a*100)}% ({n} q)")
    with c2:
        st.markdown("**Weakest topics**")
        if not weak: st.caption("—")
        for t, a, n in weak:
            st.write(f"{t} — {int(a*100)}% ({n} q)")

def view_topics():
    st.markdown("<div class='section-title'>Score Topics</div>", unsafe_allow_html=True)

    cats = get_category_map()
    q_count = questions_count_by_topic()
    prog = load_progress()

    # Category header (top) + search (like your earlier layout)
    cat_names = ["All"] + list(cats.keys())
    # Build manual pill bar to keep your previous aesthetic (instead of segmented_control)
    current_cat = st.session_state.get("cat_filter", "All")
    pill_cols = st.columns(len(cat_names))
    for i, name in enumerate(cat_names):
        with pill_cols[i]:
            active = (name == current_cat)
            html = f"<a class='cat-pill{' active' if active else ''}' href='?cat={i}'>{name}</a>"
            st.markdown(html, unsafe_allow_html=True)

    # Read cat selection from query (so pills work without reflow glitches)
    qp = dict(st.query_params)
    if "cat" in qp:
        try:
            idx = int(qp["cat"])
            if 0 <= idx < len(cat_names):
                current_cat = cat_names[idx]
                st.session_state["cat_filter"] = current_cat
        except Exception:
            pass
        # Clear param after capture
        st.query_params.clear()

    # Search box
    q = st.text_input("Search topics", placeholder="Search…", label_visibility="collapsed").strip().lower()

    # Compose topic list
    topics = []
    for cat, arr in cats.items():
        if current_cat != "All" and cat != current_cat:
            continue
        for t in arr:
            if q and q not in t.lower():
                continue
            topics.append(t)

    if not topics:
        st.info("No topics match your filter.")
        return

    # Render in the compact 3-column grid you liked
    st.markdown("<div class='topics-grid'>", unsafe_allow_html=True)
    for t in topics:
        _render_topic_card(t, q_count, prog)
    st.markdown("</div>", unsafe_allow_html=True)

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
    st.markdown(f"<a class='btn sm' href='?action=quiz&topic={topic_to_slug(topic)}'>Quiz this topic ▶</a>", unsafe_allow_html=True)

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
    default_idx = None
    if row["id"] in st.session_state.quiz_answers:
        try:
            default_idx = letters.index(st.session_state.quiz_answers[row["id"]])
        except Exception:
            default_idx = None
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
        verdict_class = "verdict-ok" if is_correct else "verdict-err"
        verdict_text = "Correct" if is_correct else "Incorrect"
        st.markdown(f"<span class='verdict {verdict_class}'>{verdict_text}</span>", unsafe_allow_html=True)
        if str(row["explanation"]).strip():
            st.markdown(row["explanation"], unsafe_allow_html=True)
        # Log attempt once
        key = f"scored_{row['id']}"
        if not st.session_state.get(key, False):
            record_attempt(row.get("subject",""), row["id"], is_correct)
            if st.session_state.get("quiz_mode") == "spaced":
                sr_update(row["id"], is_correct)
            st.session_state[key] = True

    if st.session_state.quiz_finished:
        correct_n = 0
        revealed_n = 0
        idx = pool.set_index("id")
        for qid, ans in st.session_state.quiz_answers.items():
            if qid in st.session_state.quiz_revealed:
                revealed_n += 1
                try:
                    if idx.loc[qid]["correct"] == ans:
                        correct_n += 1
                except Exception:
                    pass
        st.success(f"Score: {correct_n}/{revealed_n if revealed_n else len(pool)}")

# ------------------ Router ------------------
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
