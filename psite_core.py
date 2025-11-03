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

st.set_page_config(page_title="PSITE Mastery", page_icon=None, layout="wide", initial_sidebar_state="expanded")
apply_base_theme()
ensure_session_keys()
try_auto_login_persisted()

# ------------------ Header ------------------
st.markdown("""
<div class="app-header">
  <div class="app-header-inner">
    <div class="app-brand"><div class="app-title">PSITE Mastery</div></div>
    <div></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ------------------ Auth Gate ------------------
if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, and quizzes.")
    auth_login_form()
    st.stop()

# ------------------ Action Router via query params (for HTML buttons) ------------------
def _consume_action_query():
    qp = dict(st.query_params)
    action = qp.get("action")
    slug = qp.get("topic")
    if action and slug:
        topic = slug_to_topic(slug)
        # Clear action so we don't loop
        st.query_params.clear()
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
def _topics_flat():
    cats = get_category_map()
    return [(cat, t) for cat, arr in cats.items() for t in arr]

def _render_topic_card(topic: str, q_total_map: dict, progress_map: dict):
    # Progress
    total_q = int(q_total_map.get(topic, 0))
    attempted = int(progress_map.get(topic, {}).get("total", 0))
    pct_done = int(100 * attempted / total_q) if total_q else 0

    # Readiness signals
    review_words = get_review_word_count(topic)
    has_review = review_words >= 250
    has_quiz   = total_q >= 5

    # Compose button classes
    review_cls = "btn sm" + (" green" if has_review else "")
    quiz_cls   = "btn sm" + (" green" if has_quiz else "")

    slug = topic_to_slug(topic)
    # Single-bubble card with title, progress bar, and 2 compact buttons
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
    df = df.sample(n=min(len(df), int(n)), random_state=42).reset_index(drop=True) if not df.empty else df
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
    acc = overall_accuracy()
    st.metric("Overall Correct", f"{int(round(acc*100))}%")

    series = accuracy_timeseries(days=30)
    if series:
        dates = [d for d,_,_ in series]
        accs  = [a for _,a,_ in series]
        counts= [n for _,_,n in series]
        import matplotlib.pyplot as plt
        fig1 = plt.figure()
        plt.plot(dates, [a*100 for a in accs])
        plt.xticks(rotation=45, ha="right")
        plt.ylabel("% Correct")
        plt.title("Last 30 days")
        st.pyplot(fig1, clear_figure=True)

        # Questions per day
        fig2 = plt.figure()
        plt.bar(dates, counts)
        plt.xticks(rotation=45, ha="right")
        plt.ylabel("Questions / day")
        plt.title("Attempts per day")
        st.pyplot(fig2, clear_figure=True)
    else:
        st.info("No attempts yet. Start a quiz to build your trend.")

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

    # Top header: category selector & search
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

    # Render cards in 3 columns, but one compact bubble per topic (title+bar+buttons)
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
    st.markdown(f"<a class='btn sm' href='?action=quiz&topic={topic_to_slug(topic)}'>Quiz this topic ▶</a>", unsafe_allow_html=True)

def view_make_quiz():
    st.markdown("<div class='section-title'>Make a Quiz</div>", unsafe_allow_html=True)
    topics = ["Any"] + get_topics()
    pick = st.multiselect("Choose topics (or leave empty for Any):", topics, default=[])
    n = st.number_input("Number of questions", 5, 100, 20, step=5)
    if st.button("Start ▶", use_container_width=True):
        if pick and "Any" in pick: pick = []
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
    default_idx = letters.index(st.session_state.quiz_answers[row["id"]]) if row["id"] in st.session_state.quiz_answers else None
    choice = st.radio("", letters, index=default_idx, format_func=lambda L: row[L], label_visibility="collapsed", key=f"q_{row['id']}")
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
        correct_n = sum(
            1 for qid, ans in st.session_state.quiz_answers.items()
            if pool.set_index("id").loc[qid]["correct"] == ans and qid in st.session_state.quiz_revealed
        )
        revealed_n = sum(1 for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed)
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
