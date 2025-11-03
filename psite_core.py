# psite_core.py
import os, re, glob, json, time, secrets, base64, hashlib, hmac, datetime as dt
from typing import Dict, List, Tuple, Optional
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Optional cookie manager
COOKIE_AVAILABLE = True
try:
    from streamlit_cookies_manager import EncryptedCookieManager
except Exception:
    COOKIE_AVAILABLE = False

# ============================== PATHS ==============================
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(BASE_DIR, "data")
QUESTIONS_DIR = os.path.join(DATA_DIR, "questions")
REVIEWS_DIR   = os.path.join(DATA_DIR, "reviews")
STATE_DIR     = os.path.join(DATA_DIR, "state")
USERS_JSON    = os.path.join(STATE_DIR, "users.json")
SECRET_FILE   = os.path.join(STATE_DIR, "secret.key")
THEME_CSS     = os.path.join(BASE_DIR, "theme.css")

for p in [DATA_DIR, QUESTIONS_DIR, REVIEWS_DIR, STATE_DIR]:
    os.makedirs(p, exist_ok=True)

CREATE_TOPIC_DIRS = True

# ============================== THEME ==============================
def apply_base_theme():
    if os.path.exists(THEME_CSS):
        with open(THEME_CSS, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    st.markdown("""
    <style>
      /* Sidebar should not reserve dead space when collapsed */
      [data-testid="stSidebar"] { min-width: 300px !important; width: 300px !important; }
      .stSidebar.collapsed ~ div[data-testid="stMain"] .block-container { max-width: 1200px !important; }

      :root { --header-h: 64px; --accent:#1d4ed8; --border:#eef0f3; --ok:#10b981; --bg:#ffffff; --muted:#6b7280; }
      header { visibility:hidden; height:0!important; }
      .app-header{position:fixed;top:0;left:0;right:0;height:var(--header-h);background:#fff;
        border-bottom:1px solid var(--border);z-index:1000;display:flex;align-items:center;}
      .app-header-inner{max-width:1200px;margin:0 auto;width:100%;padding:0 12px;
        display:flex;align-items:center;justify-content:space-between;}
      .app-title{font-weight:800;font-size:1.08rem; white-space:nowrap;}
      .block-container{padding-top:calc(var(--header-h) + 12px)!important;}

      .section-title{font-weight:700;margin:.2rem 0 .5rem 0;}
      .divider{height:1px;background:var(--border);margin:1rem 0;}

      .topic-card{border:1px solid var(--border);border-radius:14px;background:var(--bg);
        padding:.9rem .9rem .7rem .9rem; box-shadow:0 1px 4px rgba(0,0,0,.03);
        display:flex;flex-direction:column;gap:.55rem;}
      .topic-title{font-weight:700;font-size:1rem;line-height:1.25;}
      .topic-row{display:flex;align-items:center;gap:.6rem;}
      .meter{flex:1;height:8px;background:#f2f5fb;border-radius:999px;overflow:hidden;}
      .meter>span{display:block;height:100%;background:var(--accent);width:0%;}
      .topic-actions{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;}
      .btn{border:1px solid #dbe2ea;border-radius:10px;padding:.28rem .55rem;background:#fff;
           cursor:pointer;font-size:.80rem;line-height:1.1; text-decoration:none; color:#111;}
      .btn.sm{padding:.22rem .5rem;font-size:.78rem;border-radius:9px;}
      .btn.green{background:var(--ok); color:#fff; border-color:#18c08d;}
      .btn:hover{filter:brightness(0.98);}
      .topic-meta{font-size:.82rem;color:var(--muted);}

      .pill{border:1px solid #dbe2ea;border-radius:999px;padding:.28rem .6rem;background:#fff;cursor:pointer;font-size:.85rem;}
      .pill.secondary{background:#f7f9fc;}

      .q-prompt { border:1px solid var(--border); background:#fafbfc; border-radius:10px; padding:12px; margin-bottom:6px; }
      .verdict { font-weight:600; padding:.22rem .6rem; border-radius:999px; border:1px solid transparent; display:inline-flex; align-items:center; }
      .verdict-ok  { background:#10b9811a; color:#065f46; border-color:#34d399; }
      .verdict-err { background:#ef44441a; color:#7f1d1d; border-color:#fca5a5; }
    </style>
    """, unsafe_allow_html=True)

# ============================== JSON I/O ==============================
def _read_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================== SECRET / TOKENS ==============================
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
    if not token or "." not in token: return None
    payload_b64, sig = token.split(".", 1)
    if not hmac.compare_digest(_sign(payload_b64), sig): return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()): return None
    return payload.get("u")

# ============================== COOKIES / URL / LOCALSTORAGE ==============================
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
    try: return dict(st.query_params)
    except Exception: return {k: (v[0] if isinstance(v, list) and v else v) for k,v in st.experimental_get_query_params().items()}

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
      try { const url=new URL(window.location); url.searchParams.delete('t');
            window.history.replaceState(null,'',url.toString()); } catch(e){}
    </script>
    """, height=0)

def try_auto_login_persisted():
    if st.session_state.get("auth_user"): return
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

# ============================== AUTH ==============================
def _hash_pw(password: str, salt_b64: Optional[str] = None) -> Tuple[str, str]:
    salt = base64.b64decode(salt_b64) if salt_b64 else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000, dklen=32)
    return base64.b64encode(dk).decode(), base64.b64encode(salt).decode()

def _verify_pw(password: str, salt_b64: str, hash_b64: str) -> bool:
    calc, _ = _hash_pw(password, salt_b64)
    return hmac.compare_digest(calc, hash_b64)

def auth_is_authed() -> bool:
    return bool(st.session_state.get("auth_user"))

def auth_user_dir(username: str) -> str:
    p = os.path.join(STATE_DIR, "users", re.sub(r"[^A-Za-z0-9_.-]+", "_", username))
    os.makedirs(p, exist_ok=True); return p

def _user_paths(username: str) -> Dict[str, str]:
    base = auth_user_dir(username)
    return {
        "progress": os.path.join(base, "progress.json"),
        "history":  os.path.join(base, "history.json"),
        "sr":       os.path.join(base, "sr.json"),
    }

def auth_login_form():
    st.markdown("<div class='topic-card'><b>Login</b></div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Sign in", "Create account"])
    with tab1:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            remember = st.checkbox("Remember me", value=True)
            if st.form_submit_button("Sign in"):
                users = _read_json(USERS_JSON, {})
                rec = users.get(u)
                if not rec or not _verify_pw(p, rec["salt"], rec["hash"]):
                    st.error("Invalid username or password.")
                else:
                    persist_login(u, remember_days=(7 if remember else 1))
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
                    users = _read_json(USERS_JSON, {})
                    if u in users:
                        st.error("Username is taken.")
                    else:
                        h, s = _hash_pw(p1)
                        users[u] = {"hash": h, "salt": s, "created": int(time.time())}
                        _write_json(USERS_JSON, users)
                        _ = auth_user_dir(u)
                        st.success("Account created. Please sign in.")
                        st.rerun()

def auth_logout_button():
    if st.button("Logout", type="secondary"):
        clear_persisted_login(); st.rerun()

# ============================== SCORE TOPICS ==============================
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
    "Category 2: GI, Hepatobiliary, Abdominal Wall, Fetal": [
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
ALL_TOPICS: List[str] = [t for cat in CATEGORY_TO_TOPICS.values() for t in cat]
def get_topics() -> List[str]: return ALL_TOPICS
def get_category_map() -> dict: return CATEGORY_TO_TOPICS

# Helpers for slug <-> topic
def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:120]

TOPIC_TO_SLUG = {t: slugify(t) for t in ALL_TOPICS}
SLUG_TO_TOPIC = {v: k for k, v in TOPIC_TO_SLUG.items()}
def topic_to_slug(topic: str) -> str: return TOPIC_TO_SLUG.get(topic, slugify(topic))
def slug_to_topic(slug: str) -> Optional[str]: return SLUG_TO_TOPIC.get(slug)

def ensure_topic_dirs():
    if not CREATE_TOPIC_DIRS: return
    for t, slug in TOPIC_TO_SLUG.items():
        os.makedirs(os.path.join(QUESTIONS_DIR, slug), exist_ok=True)

ensure_topic_dirs()

# ============================== QUESTIONS / REVIEWS ==============================
FRONTMATTER_RE = re.compile(r"^---\s*([\s\S]*?)\s*---\s*([\s\S]*)$", re.MULTILINE)
EXPL_SPLIT_RE  = re.compile(r"<!--\s*EXPLANATION\s*-->", re.IGNORECASE)
REQUIRED_COLS  = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

def parse_front_matter(text: str) -> Tuple[Dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m: raise ValueError("Missing front-matter '--- ... ---'")
    fm, body = m.group(1), m.group(2)
    meta: Dict[str, str] = {}
    for line in fm.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body.strip()

def split_stem_explanation(body: str) -> Tuple[str, str]:
    parts = EXPL_SPLIT_RE.split(body, maxsplit=1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (body.strip(), "")

def _infer_subject_from_path(path: str) -> Optional[str]:
    parent = os.path.basename(os.path.dirname(path)).lower()
    return SLUG_TO_TOPIC.get(parent)

def load_questions_frame() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(QUESTIONS_DIR, "**", "*.md"), recursive=True))
    rows = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as h:
                raw = h.read()
            meta, body = parse_front_matter(raw)
            stem, explanation = split_stem_explanation(body)
            subject = (meta.get("subject","") or "").strip()
            if not subject:
                subject = _infer_subject_from_path(f) or ""
            rec = {
                "id": meta.get("id","").strip(),
                "subject": subject,
                "A": meta.get("A","").strip(),
                "B": meta.get("B","").strip(),
                "C": meta.get("C","").strip(),
                "D": meta.get("D","").strip(),
                "E": meta.get("E","").strip(),
                "correct": meta.get("correct","").strip().upper(),
                "stem": stem, "explanation": explanation,
            }
            if rec["id"] and rec["correct"] and rec["stem"] and rec["subject"]:
                rows.append(rec)
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df = pd.DataFrame(rows)
    for c in REQUIRED_COLS:
        if c not in df.columns: df[c] = ""
        df[c] = df[c].astype(str).str.strip()
    df["correct"] = df["correct"].str.upper()
    df = df[df["subject"].isin(get_topics())].copy()
    return df.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)

def load_questions_for_subjects(subjects: List[str]) -> pd.DataFrame:
    if not subjects: return load_questions_frame()
    df = load_questions_frame()
    if df.empty: return df
    return df[df["subject"].isin(subjects)].reset_index(drop=True)

def resolve_review_path(topic: str) -> Optional[str]:
    slug = TOPIC_TO_SLUG.get(topic, slugify(topic))
    exact = os.path.join(REVIEWS_DIR, f"{slug}.md")
    if os.path.exists(exact): return exact
    alt = os.path.join(REVIEWS_DIR, f"{topic}.md")
    if os.path.exists(alt): return alt
    for p in sorted(glob.glob(os.path.join(REVIEWS_DIR, "*.md"))):
        base = os.path.splitext(os.path.basename(p))[0].lower()
        if base.startswith(slug): return p
    return None

def get_review_word_count(topic: str) -> int:
    """Return word count of the review markdown for the topic, 0 if missing."""
    p = resolve_review_path(topic)
    if not p: return 0
    try:
        with open(p, "r", encoding="utf-8") as f:
            txt = f.read()
        # crude word count (strip code fences/links)
        txt = re.sub(r"```[\\s\\S]*?```", " ", txt)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"\\[.*?\\]\\(.*?\\)", " ", txt)
        words = re.findall(r"[A-Za-z0-9_’']+", txt)
        return len(words)
    except Exception:
        return 0

def questions_count_by_topic() -> Dict[str, int]:
    df = load_questions_frame()
    if df.empty: return {t:0 for t in get_topics()}
    return df.groupby("subject")["id"].nunique().to_dict()

# ============================== USER STATE / ANALYTICS ==============================
def _user_file(pathkey: str) -> str:
    u = st.session_state.get("auth_user")
    if not u: raise RuntimeError("Not authenticated.")
    base = auth_user_dir(u)
    paths = {
        "progress": os.path.join(base, "progress.json"),
        "history":  os.path.join(base, "history.json"),
        "sr":       os.path.join(base, "sr.json"),
    }
    return paths[pathkey]

def load_progress() -> Dict[str, Dict]:
    topics = get_topics()
    data = _read_json(_user_file("progress"), {})
    for t in topics:
        data.setdefault(t, {"completed": False, "correct": 0, "total": 0, "last_seen": None, "mastered": False})
    for k in list(data.keys()):
        if k not in topics: data.pop(k, None)
    return data

def save_progress(d: Dict[str, Dict]): _write_json(_user_file("progress"), d)

def load_history() -> List[Dict]: return _read_json(_user_file("history"), [])
def save_history(arr: List[Dict]): _write_json(_user_file("history"), arr)

def record_attempt(topic: str, qid: str, correct: bool):
    hist = load_history()
    hist.append({"ts": int(time.time()), "topic": topic, "id": qid, "correct": bool(correct)})
    save_history(hist)
    prog = load_progress()
    rec = prog.setdefault(topic, {"completed": False, "correct": 0, "total": 0, "last_seen": None, "mastered": False})
    rec["total"] += 1
    if correct: rec["correct"] += 1
    rec["last_seen"] = int(time.time())
    if rec["total"] >= 5 and rec["correct"]/max(1,rec["total"]) >= 0.8:
        rec["mastered"] = True
    save_progress(prog)

def overall_accuracy() -> float:
    prog = load_progress()
    tot = sum(v.get("total",0) for v in prog.values())
    cor = sum(v.get("correct",0) for v in prog.values())
    return (cor / tot) if tot else 0.0

def accuracy_timeseries(days: int = 30) -> List[Tuple[str,float,int]]:
    hist = load_history()
    if not hist: return []
    today = dt.date.today()
    by_day = {}
    for i in range(days-1, -1, -1):
        d = today - dt.timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        by_day[key] = {"c":0, "t":0}
    for h in hist:
        d = dt.datetime.fromtimestamp(h["ts"]).date().strftime("%Y-%m-%d")
        if d in by_day:
            by_day[d]["t"] += 1
            by_day[d]["c"] += int(bool(h["correct"]))
    seq = []
    for d, rec in by_day.items():
        acc = (rec["c"]/rec["t"]) if rec["t"] else 0.0
        seq.append((d, acc, rec["t"]))
    return seq

def topic_strengths(k:int=5) -> Tuple[List[Tuple[str,float,int]], List[Tuple[str,float,int]]]:
    prog = load_progress()
    items = []
    for t, rec in prog.items():
        n = rec.get("total",0)
        acc = (rec.get("correct",0) / n) if n else 0.0
        items.append((t, acc, n))
    tried = [x for x in items if x[2] >= 5] or items
    weakest = sorted(tried, key=lambda x: x[1])[:k]
    strongest = sorted(tried, key=lambda x: x[1], reverse=True)[:k]
    return strongest, weakest

# ============================== SR (SM-2 lite) ==============================
def _now_day_ts() -> int:
    today = dt.date.today()
    return int(time.mktime(dt.datetime(today.year,today.month,today.day).timetuple()))

def load_sr() -> Dict[str, Dict]: return _read_json(_user_file("sr"), {})
def save_sr(srobj: Dict[str, Dict]): _write_json(_user_file("sr"), srobj)

def _init_sr_if_needed(qid: str):
    sr = load_sr()
    if qid not in sr:
        sr[qid] = {"reps": 0, "interval": 0.0, "ease": 2.5, "due_ts": _now_day_ts(), "last_result": None}
        save_sr(sr)

def sr_due_ids(limit:int=20, subjects: Optional[List[str]]=None) -> List[str]:
    df = load_questions_for_subjects(subjects or [])
    if df.empty: return []
    sr = load_sr(); today = _now_day_ts(); ids=[]
    for _, r in df.iterrows():
        qid = r["id"]; d = sr.get(qid); due_ts = d["due_ts"] if d else today
        if due_ts <= today: ids.append(qid)
    if not ids:
        upcoming = sorted(((q, sr.get(q, {"due_ts":today})["due_ts"]) for q in df["id"].tolist()), key=lambda x:x[1])
        ids = [q for q,_ in upcoming[:limit]]
    return ids[:limit]

def sr_update(qid:str, was_correct:bool):
    _init_sr_if_needed(qid)
    sr = load_sr(); rec = sr[qid]
    quality = 4 if was_correct else 2
    ease = rec.get("ease",2.5); reps = rec.get("reps",0); interval = rec.get("interval",0.0)
    if was_correct:
        if reps==0: interval=1
        elif reps==1: interval=6
        else: interval=round(interval*ease)
        reps += 1
        ease = max(1.3, ease + 0.1 - (5-quality)*(0.08 + (5-quality)*0.02))
    else:
        reps = 0; interval = 1; ease = max(1.3, ease - 0.2)
    due_date = dt.date.today() + dt.timedelta(days=int(interval))
    due_ts = int(time.mktime(dt.datetime(due_date.year,due_date.month,due_date.day).timetuple()))
    rec.update({"reps":reps,"interval":float(interval),"ease":float(ease),"due_ts":due_ts,"last_result":int(was_correct)})
    sr[qid]=rec; save_sr(sr)

# ============================== SESSION DEFAULTS ==============================
def ensure_session_keys():
    st.session_state.setdefault("auth_user", None)
    st.session_state.setdefault("view", "dashboard")
    st.session_state.setdefault("active_topic", None)
    st.session_state.setdefault("quiz_mode", "normal")
    st.session_state.setdefault("quiz_pool", None)
    st.session_state.setdefault("quiz_idx", 0)
    st.session_state.setdefault("quiz_answers", {})
    st.session_state.setdefault("quiz_revealed", set())
    st.session_state.setdefault("quiz_finished", False)
