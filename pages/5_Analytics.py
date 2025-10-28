import streamlit as st
import pandas as pd
from psite_core import apply_base_theme, load_progress, get_topics

st.set_page_config(page_title="Analytics — PSITE Mastery", layout="wide")
apply_base_theme()

st.markdown("<div class='psite-title'>Analytics</div>", unsafe_allow_html=True)
prog = load_progress()
rows = []
for t in get_topics():
    rec = prog.get(t, {})
    total = rec.get("total", 0)
    acc = (rec.get("correct",0)/total) if total else 0.0
    rows.append({
        "Topic": t,
        "Attempts": total,
        "Accuracy": round(acc*100),
        "Completed": bool(rec.get("completed")),
        "Mastered": bool(rec.get("mastered")),
    })
df = pd.DataFrame(rows)

col1, col2 = st.columns([2,3])
with col1:
    st.dataframe(df.sort_values(["Mastered","Accuracy","Attempts"], ascending=[False,False,False]),
                 use_container_width=True)
with col2:
    st.bar_chart(df.set_index("Topic")["Accuracy"])
