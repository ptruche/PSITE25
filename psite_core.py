# psite_core.py
import os, re, glob, json, time, secrets, base64, hashlib, hmac, datetime as dt
from typing import Dict, List, Tuple, Optional
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ------------------------------------------------------------------ #
# PATHS
# ------------------------------------------------------------------ #
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(BASE_DIR, "data")
QUESTIONS_DIR = os.path.join(DATA_DIR, "questions")
REVIEWS_DIR   = os.path.join(DATA_DIR, "reviews")
STATE_DIR     = os.path.join(DATA_DIR, "state")
USERS_JSON    = os.path.join(STATE_DIR, "users.json")
SECRET_FILE   = os.path.join(STATE_DIR, "secret.key")

for p in [DATA_DIR, QUESTIONS_DIR, REVIEWS_DIR, STATE_DIR]:
    os.makedirs(p, exist_ok=True)

COOKIE_AVAILABLE = True
try:
    from streamlit_cookies_manager import EncryptedCookieManager  # optional
except Exception:
    COOKIE_AVAILABLE = False

# ------------------------------------------------------------------ #
# THEME (only the CSS variables – UI lives in app.py)
# ------------------------------------------------------------------ #
def apply_base_theme():
    st.markdown(
        "<style>:root{--accent:#1d4ed8;--border:#e5e7eb;--bg:#fff;--text:#111;}</style>",
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------ #
# APP SECRET / TOKENS
# ------------------------------------------------------------------ #
def _get_app_secret() -> bytes:
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "rb") as f:
            return f.read()
    secret = secrets.token_bytes(32)
    os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)
    with open(SECRET_FILE, "wb") as f:
        f.write(secret)
    return secret

def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def _sign(payload_b64: str) -> str:
    sig = hmac.new(_get_app_secret(), payload_b64.encode(), hashlib.sha256).digest()
    return _b64url_encode(sig)

def issue_auth_token(username: str, days_valid: int = 7) -> str:
    payload = {"u": username, "exp": int(time.time()) + days_valid*86400}
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",",":")).encode())
    sig = _sign(payload_b64)
    return f"{payload_b64}.{sig}"

def verify_auth_token(token: str) -> Optional[str]:
    if not token or "." not in token:
        return None
    payload_b64, sig = token.split(".", 1)
    if not hmac.compare_digest(_sign(payload_b64), sig):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload.get("u")

# ------------------------------------------------------------------ #
# COOKIES / URL / LOCALSTORAGE
# ------------------------------------------------------------------ #
def _cookies():
    if COOKIE_AVAILABLE:
        cm = EncryptedCookieManager(prefix="psite_", password=_get_app_secret().hex())
        if not cm.ready():
            st.stop()
        return cm
    class _Shim:
        def __getitem__(self, k): return st.session_state.get(f"_cookie_{k}", "")
        def __setitem__(self, k, v): st.session_state[f"_cookie_{k}"] = v
        def get(self, k, default=""): return st.session_state.get(f"_cookie_{k}", default)
        def save(self): pass
    return _Shim()

def _get_query_params() -> dict:
    try:
        return dict(st.query_params)
    except Exception:
        return {k: (v[0] if isinstance(v, list) and v else v)
                for k,v in st.experimental_get_query_params().items()}

def _set_query_params(**kwargs):
    try:
        qp = dict(st.query_params)
        for k,v in kwargs.items():
            if v is None: qp.pop(k, None)
            else: qp[k]=v
        st.query_params.clear()
        for k,v in qp.items():
            st.query_params[k]=v
    except Exception:
        base = st.experimental_get_query_params()
        for k,v in kwargs.items():
            if v is None: base.pop(k, None)
            else: base[k]=v
        st.experimental_set_query_params(**base)

def _js_set_token(token: str):
    components.html(f"""
    <script>
      try {{
        localStorage.setItem('psite_token', {json.dumps(token)});
        const url = new URL(window.location);
        url.searchParams.set('t', {json.dumps(token)});
        window.history.replaceState(null, '', url.toString());
        window.parent.postMessage({{streamlitRerun:true}}, "*");
      }} catch (e) {{}}
    </script>
    """, height=0)

def _js_restore_token_if_missing():
    components.html("""
    <script>
      try {
        const url = new URL(window.location);
        const hasT = url.searchParams.get('t');
        const saved = localStorage.getItem('psite_token');
        if (!hasT && saved) {
          url.searchParams.set('t', saved);
          window.history.replaceState(null, '', url.toString());
          window.parent.postMessage({streamlitRerun:true}, "*");
        }
      } catch (e) {}
    </script>
    """, height=0)

def persist_login(username: str, remember_days: int = 7):
    st.session_state.auth_user = username
    token = issue_auth_token(username, remember_days)
    try:
        cm = _cookies(); cm["auth"] = token; cm.save()
    except Exception:
        pass
    _set_query_params(t=token)
    _js_set_token(token)

def clear_persisted_login():
    st.session_state.pop("auth_user", None)
    try:
        cm = _cookies(); cm["auth"] = ""; cm.save()
    except Exception:
        pass
    _set_query_params(t=None)
    components.html("""
    <script>
      try { localStorage.removeItem('psite_token'); } catch(e) {}
      try { const url = new URL(window.location);
            url.searchParams.delete('t');
            window.history.replaceState(null, '', url.toString()); } catch(e){}
      window.location.reload();
    </script>
    """, height=0)

def try_auto_login_persisted():
    if st.session_state.get("auth_user"):
        return
    _js_restore_token_if_missing()
    try:
        cm = _cookies(); token = cm.get("auth")
        user = verify_auth_token(token) if token else None
        if user:
            st.session_state.auth_user = user
            return
    except Exception:
        pass
    token = _get_query_params().get("t")
    user = verify_auth_token(token) if token else None
    if user:
        st.session_state.auth_user = user

def auth_is_authed() -> bool:
    return bool(st.session_state.get("auth_user"))

def _hash_pw(password: str, salt_b64: Optional[str] = None) -> Tuple[str, str]:
    salt = base64.b64decode(salt_b64) if salt_b64 else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000, dklen=32)
    return base64.b64encode(dk).decode(), base64.b64encode(salt).decode()

def _verify_pw(password: str, salt_b64: str, hash_b64: str) -> bool:
    calc, _ = _hash_pw(password, salt_b64)
    return hmac.compare_digest(calc, hash_b64)

def auth_login_form():
    st.markdown("<div class='topic-card'><b>Login</b></div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Sign in", "Create account"])
    with tab1:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            remember = st.checkbox("Remember me", value=True)
            if st.form_submit_button("Sign in"):
                users = json.load(open(USERS_JSON, "r", encoding="utf-8")) if os.path.exists(USERS_JSON) else {}
                rec = users.get(u)
                if not rec or not _verify_pw(p, rec["salt"], rec["hash"]):
                    st.error("Invalid username or password.")
                else:
                    persist_login(u, remember_days=(365 if remember else 1))  # Extended for "remember me"
                    st.rerun()
    with tab2:
        with st.form("create_form"):
            u = st.text_input("New username")
            p1 = st.text_input("Password", type="password")
            p2 = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Create account"):
                if not u or not p1:
                    st.error("Username and password required.")
                elif p1 != p2:
                    st.error("Passwords do not match.")
                else:
                    users = json.load(open(USERS_JSON, "r", encoding="utf-8")) if os.path.exists(USERS_JSON) else {}
                    if u in users:
                        st.error("Username is taken.")
                    else:
                        h, s = _hash_pw(p1)
                        users[u] = {"hash": h, "salt": s, "created": int(time.time())}
                        json.dump(users, open(USERS_JSON, "w", encoding="utf-8"), indent=2)
                        st.success("Account created. Please sign in.")

def auth_logout_button():
    if st.button("Logout", type="secondary", use_container_width=True):
        clear_persisted_login()
        st.rerun()

# ------------------------------------------------------------------ #
# TOPIC CATALOG
# ------------------------------------------------------------------ #
CATEGORY_TO_TOPICS = {
    "Category 1: Thoracic, Pulmonary, Airway, Chest Wall": [
        "Bronchoscopy",
        "Chest Wall Deformities: Pectus Excavatum/Carinatum, Marfan’s and Poland’s Syndromes",
        "Chylothorax","Congenital Diaphragmatic Hernia","Cystic Diseases of the Lung",
        "Cystic Fibrosis","Cystic Pulmonary Airway Malformation","Empyema",
        "Esophageal Atresia and Tracheoesophageal Fistula","Esophageal Perforation",
        "Esophageal Replacement","Esophageal Stenosis, Webs, Diverticuli",
        "Esophageal Stricture: Caustic Ingestion and Other Causes","Esophagoscopy",
        "Eventration of the Diaphragm","Gastroesophageal Reflux/Barrett's Esophagus",
        "Laryngomalacia","Lobar Emphysema","Mediastinal Cysts, Masses","Patent Ductus Arteriosus",
        "Pneumothorax","Prenatal Anomalies and Therapy","Pulmonary Abscess",
        "Pulmonary Hypoplasia/Hypertension","Pulmonary Sequestration",
        "Subacute Bacterial Endocarditis Prophylaxis","Tracheobronchial Foreign Bodies",
        "Tracheomalacia","Vascular Ring and Pulmonary Artery Sling",
    ],
    "Category 2: GI, Hepatobiliary, Abdominal Wall. Fetal": [
        "Abdominal Pain","Alimentary Tract Duplications","Appendicitis","Ascites: Chylous",
        "Biliary Atresia","Choledochal Cysts","Cloacal Exstrophy/Bladder Exstrophy",
        "Duodenal Atresia/Stenosis/Webs/Annular Pancreas","Gallbladder Disease, Gallstones",
        "Gastric Volvulus","Gastrointestinal Bleeding","Gastroschisis",
        "Hepatic Infections: Hepatitis, Abscess, Cysts","Hirschsprung Disease","Hypertrophic Pyloric Stenosis",
        "Inflammatory Bowel Disease","Inguinal Hernia","Intestinal Atresia","Intussusception","Malrotation",
        "Meconium Ileus/Peritonitis/Plug","Mesenteric and Omental Cysts","Necrotizing Enterocolitis",
        "Neonatal Gastric Perforation","Neonatal Obstruction","Omphalocele",
        "Omphalomesenteric Duct Remnants, Urachus, and Meckel's","Peptic Ulcer Disease","Polyps",
        "Portal Hypertension","Umbilical Hernia and Other Umbilical Disorders",
    ],
    "Category 3: Head/Neck, Endocrine, Breast, GU, Anorectal": [
        "Adrenal Cortical Tumors, Pheochromocytoma",
        "Anal Pathology: Fissures, Abscesses, Fistulae, Pilonidal, Prolapse",
        "Anorectal Malformation","Arterial Diseases and Vasculitis","Branchial Cleft, Arch Anomalies",
        "Breast Disorders","Circumcision and Abnormalities of the Urethra, Penis, Scrotum",
        "Disorders of Sexual Development","Endocrine Diseases","Lymphadenopathy, Atypical Mycobacteria",
        "Neurological: Shunt Complications, Dermal Sinuses","Ovarian Torsion, Cysts, and Tumors",
        "Renal Diseases: Nephrotic Syndrome, DI, Renal Vein Thrombosis, Chronic Failure, Prune Belly Syndrome",
        "Thyroglossal Duct Cyst/Sinus","Thyroid Nodules","Torsions: Appendix Testes, Testicular",
        "Torticollis","Undescended Testicle (Cryptorchidism)","Vaginal Atresia, Hydrometrocolpos","Vascular Anomalies",
    ],
    "Category 4: Trauma and Critical Care, Metabolism, Surgical Emergencies": [
        "Abdominal Trauma","Acute Renal Failure","ARDS",
        "Burns: Resuscitation, Airway, Electrical, Nutrition, Wound, Sepsis",
        "Cardiovascular Trauma: Tamponade, Contusion, Arch Disruption, Peripheral Vascular Injuries",
        "Coagulation","Extracorporeal Life Support","Fluids and Electrolytes",
        "Hematologic Diseases: Spherocytosis, Sickle Cell, ITP, HSP",
        "Lung Physiology, Pathophysiology, Ventilators, Pneumonia",
        "Musculoskeletal Trauma: Pelvis, Long Bone",
        "Neonatal Physiology and Pathophysiology: Transition from Fetal Circulation, Cardiovascular Monitoring, Shock",
        "Neurosurgical Trauma","Nonaccidental Injuries: Diagnosis, Evaluation, Legal Issues",
        "Nutrition","Obesity","Pediatric Anesthesia and Pain Management",
        "Short Bowel Syndrome/Intestinal Failure","Soft Tissue Trauma: Tetanus, Bites, Wound Infection, Crush Injuries",
        "Thoracic Trauma","Transplantation","Trauma: Initial Assessment and Resuscitation",
    ],
    "Category 5: Cancer, Tumors, Spleen": [
        "Abdominal Mass in the Newborn","Adrenal Cancer",
        "Benign Liver Tumors: Hepatic Mesenchymal Hamartoma/Adenoma/FNH",
        "Bone Tumors: Osteogenic Sarcoma, Ewing Sarcoma",
        "Chemo/Radiation Therapy, Immunotherapy Concepts, Genetics",
        "Dermoid/Epidermoid Cysts, Soft Tissue Nodules","Gastrointestinal Tumors",
        "Lung and Chest Wall Tumors","Lymphoma/Leukemia",
        "Malignant Liver Tumors: Hepatoblastoma/Hepatocellular Carcinoma",
        "Mesoblastic Nephroma","Neuroblastoma","Nevi, Melanoma",
        "Ovarian and Adnexal Problems","Rhabdomyosarcoma","Splenic Diseases","Teratoma",
        "Testicular Tumors","Wilms Tumor, Renal Cell Carcinoma, and Hemihypertrophy",
    ],
}
ALL_TOPICS = [t for cat in CATEGORY_TO_TOPICS.values() for t in cat]

ORDERED_TOPICS = [
    # Category 1
    "Prenatal Anomalies and Therapy",
    "Congenital Diaphragmatic Hernia",
    "Pulmonary Hypoplasia/Hypertension",
    "Cystic Pulmonary Airway Malformation",
    "Lobar Emphysema",
    "Pulmonary Sequestration",
    "Cystic Diseases of the Lung",
    "Lung Physiology, Pathophysiology, Ventilators, Pneumonia",
    "Pulmonary Abscess",
    "Empyema",
    "Pneumothorax",
    "Chylothorax",
    "Esophageal Atresia and Tracheoesophageal Fistula",
    "Tracheobronchial Foreign Bodies",
    "Tracheomalacia",
    "Laryngomalacia",
    "Vascular Ring and Pulmonary Artery Sling",
    "Esophageal Stricture: Caustic Ingestion and Other Causes",
    "Esophageal Stenosis, Webs, Diverticuli",
    "Gastroesophageal Reflux/Barrett's Esophagus",
    "Esophageal Perforation",
    "Esophageal Replacement",
    "Esophagoscopy",
    "Bronchoscopy",
    "Eventration of the Diaphragm",
    "Patent Ductus Arteriosus",
    "Subacute Bacterial Endocarditis Prophylaxis",
    "Cystic Fibrosis",
    "Mediastinal Cysts, Masses",
    "Chest Wall Deformities: Pectus Excavatum/Carinatum, Marfan’s and Poland’s Syndromes",

    # Category 2
    "Neonatal Physiology and Pathophysiology: Transition from Fetal Circulation, Cardiovascular Monitoring, Shock",
    "Neonatal Obstruction",
    "Neonatal Gastric Perforation",
    "Meconium Ileus/Peritonitis/Plug",
    "Necrotizing Enterocolitis",
    "Hypertrophic Pyloric Stenosis",
    "Duodenal Atresia/Stenosis/Webs/Annular Pancreas",
    "Intestinal Atresia",
    "Malrotation",
    "Gastric Volvulus",
    "Alimentary Tract Duplications",
    "Mesenteric and Omental Cysts",
    "Hirschsprung Disease",
    "Intussusception",
    "Appendicitis",
    "Inflammatory Bowel Disease",
    "Polyps",
    "Gastrointestinal Bleeding",
    "Peptic Ulcer Disease",
    "Biliary Atresia",
    "Choledochal Cysts",
    "Gallbladder Disease, Gallstones",
    "Portal Hypertension",
    "Hepatic Infections: Hepatitis, Abscess, Cysts",
    "Abdominal Pain",
    "Ascites: Chylous",
    "Gastroschisis",
    "Omphalocele",
    "Cloacal Exstrophy/Bladder Exstrophy",
    "Umbilical Hernia and Other Umbilical Disorders",
    "Omphalomesenteric Duct Remnants, Urachus, and Meckel's",
    "Inguinal Hernia",

    # Category 3
    "Branchial Cleft, Arch Anomalies",
    "Thyroglossal Duct Cyst/Sinus",
    "Torticollis",
    "Lymphadenopathy, Atypical Mycobacteria",
    "Endocrine Diseases",
    "Thyroid Nodules",
    "Adrenal Cortical Tumors, Pheochromocytoma",
    "Breast Disorders",
    "Vascular Anomalies",
    "Arterial Diseases and Vasculitis",
    "Disorders of Sexual Development",
    "Vaginal Atresia, Hydrometrocolpos",
    "Ovarian Torsion, Cysts, and Tumors",
    "Circumcision and Abnormalities of the Urethra, Penis, Scrotum",
    "Undescended Testicle (Cryptorchidism)",
    "Torsions: Appendix Testes, Testicular",
    "Renal Diseases: Nephrotic Syndrome, DI, Renal Vein Thrombosis, Chronic Failure, Prune Belly Syndrome",
    "Anorectal Malformation",
    "Anal Pathology: Fissures, Abscesses, Fistulae, Pilonidal, Prolapse",
    "Neurological: Shunt Complications, Dermal Sinuses",

    # Category 4
    "Trauma: Initial Assessment and Resuscitation",
    "Nonaccidental Injuries: Diagnosis, Evaluation, Legal Issues",
    "Thoracic Trauma",
    "Abdominal Trauma",
    "Cardiovascular Trauma: Tamponade, Contusion, Arch Disruption, Peripheral Vascular Injuries",
    "Musculoskeletal Trauma: Pelvis, Long Bone",
    "Neurosurgical Trauma",
    "Soft Tissue Trauma: Tetanus, Bites, Wound Infection, Crush Injuries",
    "Burns: Resuscitation, Airway, Electrical, Nutrition, Wound, Sepsis",
    "ARDS",
    "Acute Renal Failure",
    "Fluids and Electrolytes",
    "Nutrition",
    "Obesity",
    "Short Bowel Syndrome/Intestinal Failure",
    "Coagulation",
    "Hematologic Diseases: Spherocytosis, Sickle Cell, ITP, HSP",
    "Pediatric Anesthesia and Pain Management",
    "Extracorporeal Life Support",
    "Transplantation",

    # Category 5
    "Vascular Anomalies",
    "Nevi, Melanoma",
    "Dermoid/Epidermoid Cysts, Soft Tissue Nodules",
    "Lymphoma/Leukemia",
    "Neuroblastoma",
    "Wilms Tumor, Renal Cell Carcinoma, and Hemihypertrophy",
    "Mesoblastic Nephroma",
    "Testicular Tumors",
    "Ovarian and Adnexal Problems",
    "Rhabdomyosarcoma",
    "Bone Tumors: Osteogenic Sarcoma, Ewing Sarcoma",
    "Gastrointestinal Tumors",
    "Abdominal Mass in the Newborn",
    "Benign Liver Tumors: Hepatic Mesenchymal Hamartoma/Adenoma/FNH",
    "Malignant Liver Tumors: Hepatoblastoma/Hepatocellular Carcinoma",
    "Adrenal Cancer",
    "Lung and Chest Wall Tumors",
    "Teratoma",
    "Splenic Diseases",
    "Chemo/Radiation Therapy, Immunotherapy Concepts, Genetics",
]

# ---------- LEARNING PATH ----------
elif view == "learning_path":
    st.markdown("<div class='section-title'>Learning Path</div>", unsafe_allow_html=True)
    history = load_history()
    completed_ids = {h['id'] for h in history if h['correct']}

    for topic in ORDERED_TOPICS:
        ids = sorted(ALL_Q[ALL_Q['subject'] == topic]['id'].tolist())
        if not ids:
            continue
        st.markdown(f"### {topic}")
        dots_html = []
        for id in ids:
            color = "green" if id in completed_ids else ""
            dots_html.append(f"<span class='dot {color}' style='width:12px;height:12px;margin:0 4px;'></span>")
        st.markdown("<div style='display:flex;flex-wrap:wrap;'>"+ "".join(dots_html) +"</div>", unsafe_allow_html=True)
        if st.button("Start Quiz", key=f"lp_quiz_{topic}", use_container_width=True):
            pool = ALL_Q[ALL_Q['subject'] == topic].sort_values('id').reset_index(drop=True)
            _start_quiz(pool, mode="normal", topic=topic)
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

# ---------- QUIZ ----------
elif view == "quiz":
    pool: pd.DataFrame = st.session_state.get("quiz_pool")
    if pool is None or pool.empty:
        if st.session_state.get("quiz_mode") == "spaced":
            st.success("✅ No spaced-repetition items due.")
        else:
            st.info("No questions found. Add `.md` files to `data/questions/`.")
    else:
        i = st.session_state.quiz_idx
        row = pool.iloc[i]
        pct = int(((i + 1) / len(pool)) * 100)
        st.progress(pct/100)
        suffix = f" • {row.get('subject','')}" if row.get('subject') else ""
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
            _record_and_update(row, is_correct)

        if st.session_state.quiz_finished:
            idxed = pool.set_index("id")
            scored_ids = [qid for qid in st.session_state.quiz_answers if qid in st.session_state.quiz_revealed]
            correct_n = sum(1 for qid in scored_ids if idxed.loc[qid]["correct"] == st.session_state.quiz_answers[qid])
            denom = len(scored_ids) if scored_ids else len(pool)
            st.success(f"Score: {correct_n}/{denom}")

st.markdown("</div>", unsafe_allow_html=True)   # .main
