# app.py
import streamlit as st
import pandas as pd

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
/* Hard reset top spacing */
html, body { margin:0 !important; padding:0 !important; }
[data-testid="stAppViewContainer"] { padding-top:0 !important; }
main.block-container { padding-top:0 !important; margin-top:0 !important; }
header[data-testid="stHeader"], div[data-testid="stToolbar"] { display:none !important; }

/* Rail wrapper */
.edge-rail-wrap { position: sticky; top: 0; height: 100vh; }
.main-scroll { height: 100vh; overflow: auto; padding: 12px 16px 24px; }

/* Edge rail */
.edge-rail {
  width:100%; height:100%; overflow:hidden;
  background:#f5f7fb; border-right:1px solid #e7ecf3;
  padding:12px 12px; border-radius:0 12px 12px 0;
  box-shadow:1px 0 0 rgba(0,0,0,.02) inset;
  display:flex; flex-direction:column; gap:8px; justify-content:flex-start;
  transition: padding .22s ease;
}
.edge-rail.collapsed { padding:10px 8px; align-items:center; justify-content:center; }

/* Rail content */
.edge-rail-title {font-weight:900;font-size:1.05rem;letter-spacing:.2px;margin:.25rem 0 .2rem 0;}
.edge-rail-sub {color:#6b7280;font-size:.82rem;margin:.1rem 0 .4rem 0;}
.edge-rail .nav-btn {
  width:100%; border-radius:10px; padding:.48rem .65rem;
  border:1px solid #e5e7eb; background:#fff; margin-bottom:.45rem;
}
.edge-rail .sep {height:1px;background:#e9edf5;margin:.55rem 0;}

/* Tiny tab (custom HTML) */
.rail-tab {
  position: absolute !important;
  right: -12px; top: 50%; transform: translateY(-50%);
  width: 24px; height: 48px;
  background: #fff; border: 1px solid #e5e7eb;
  border-radius: 0 8px 8px 0;
  box-shadow: 2px 0 4px rgba(0,0,0,.07);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; cursor: pointer; z-index: 100;
  user-select: none;
}
.rail-tab:hover { background: #f8fafc; border-color: #cbd5e1; }

/* Other styles (unchanged) */
.kpi-card, .meter, .badge, .topic-title, .q-prompt, .verdict, .section-title, .divider { /* keep all your original styles */ }
</style>
""", unsafe_allow_html=True)

# ---------------- Auth & Session ----------------
ensure_session_keys()
try_auto_login_persisted()

if not auth_is_authed():
    st.markdown("#### Welcome")
    st.caption("Sign in to access your dashboard, topics, and quizzes.")
    auth_login_form()
    st.stop()

if "rail_open" not in st.session_state:
    st.session_state.rail_open = True

def _toggle_rail():
    st.session_state.rail_open = not st.session_state.rail_open
    st.rerun()

def _safe_pct(n, d): return int(round(100 * n / d)) if d else 0

# ---------------- (All your functions: _render_topic_card, views, etc.) ----------------
# ... [PASTE ALL YOUR ORIGINAL FUNCTIONS HERE] ...
# (I'm omitting them for brevity — keep them 100% unchanged)

# ---------------- Layout ----------------
rail_w_exp = 0.18
rail_w_col = 0.06
rail_w = rail_w_exp if st.session_state.rail_open else rail_w_col
main_w = 1.0 - rail_w

rail_col, main_col = st.columns([rail_w, main_w], gap="small")

with rail_col:
    st.markdown("<div class='edge-rail-wrap'>", unsafe_allow_html=True)
    rail_cls = "edge-rail collapsed" if not st.session_state.rail_open else "edge-rail"
    st.markdown(f"<div class='{rail_cls}' style='position:relative;'>", unsafe_allow_html=True)

    # ---- Custom HTML Tab (click triggers JS → Python) ----
    tab_icon = "Left Arrow" if st.session_state.rail_open else "Right Arrow"
    st.markdown(f"""
    <div class="rail-tab" onclick="window.parent.document.dispatchEvent(new Event('rail_toggle_click'))">
        {tab_icon}
    </div>
    """, unsafe_allow_html=True)

    # ---- JS Listener to call Python ----
    components.html(f"""
    <script>
    if (!window.railListenerAdded) {{
        window.parent.document.addEventListener('rail_toggle_click', () => {{
            Streamlit.setComponentValue('toggle');
        }});
        window.railListenerAdded = true;
    }}
    </script>
    """, height=0)

    # ---- Python catches the JS event ----
    if st._is_running_with_streamlit and 'toggle' in st.session_state:
        _toggle_rail()
        del st.session_state['toggle']

    # ---- Rail Content (only when expanded) ----
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

    st.markdown("</div>", unsafe_allow_html=True)  # end rail
    st.markdown("</div>", unsafe_allow_html=True)  # end wrap

with main_col:
    st.markdown("<div class='main-scroll'>", unsafe_allow_html=True)
    render_main()
    st.markdown("</div>", unsafe_allow_html=True)
