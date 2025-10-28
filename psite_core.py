import os, re, glob, json, time, secrets, base64, hashlib, hmac, datetime as dt
from typing import Dict, List, Tuple, Optional
import pandas as pd
import streamlit as st

# Try cookie manager; fall back safely if missing
COOKIE_AVAILABLE = True
try:
    from streamlit_cookies_manager import EncryptedCookieManager  # pip: streamlit-cookies-manager
except Exception:
    COOKIE_AVAILABLE = False

# ==========================================================
# PATHS & INITIALIZATION
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
QUESTIONS_DIR = os.path.join(DATA_DIR, "questions")
REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")
STATE_DIR = os.path.join(DATA_DIR, "state")
USERS_JSON = os.path.join(STATE_DIR, "users.json")
SECRET_FILE = os.path.join(STATE_DIR, "secret.key")    # for HMAC signing and cookie encryption
THEME_CSS = os.path.join(BASE_DIR, "theme.css")

for p in [DATA_DIR, QUESTIONS_DIR, REVIEWS_DIR, STATE_DIR]:
    os.makedirs(p, exist_ok=True)

# ==========================================================
# STYLING
# ==========================================================
def apply_base_theme():
    if os.path.exists(THEME_CSS):
        with open(THEME_CSS, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ==========================================================
# JSON HELPERS
# ==========================================================
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

# ==========================================================
# SECRET + TOKEN SIGNING
# ==========================================================
def _get_app_secret() -> bytes:
    """Stable secret across restarts for HMAC and (when available) cookie encryption."""
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
    payload = {"u": username, "exp": int(time.time()) + days_valid * 86400}
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
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

# ==========================================================
# URL PARAM HELPERS (fallback persistence)
# ==========================================================
def _get_query_params() -> dict:
    try:
        return dict(st.query_params)
    except Exception:
        return {k: v[0] if isinstance(v, list) and v else v for k, v in st.experimental_get_query_params().items()}

def _set_query_params(**kwargs):
    try:
        qp = dict(st.query_params)
        for k, v in kwargs.items():
            if v is None and k in qp:
                qp.pop(k, None)
            elif v is not None:
                qp[k] = v
        st.query_params.clear()
        for k, v in qp.items():
            st.query_params[k] = v
    except Exception:
        base = st.experimental_get_query_params()
        for k, v in kwargs.items():
            if v is None:
                base.pop(k, None)
            else:
                base[k] = v
        st.experimental_set_query_params(**base)

# ==========================================================
# COOKIES (if available) OR SAFE FALLBACK
# ==========================================================
def _cookies():
    """Return an object with dict-like get/set/save API. Falls back if lib missing."""
    if COOKIE_AVAILABLE:
        cm = EncryptedCookieManager(prefix="psite_", password=_get_app_secret().hex())
        if not cm.ready():
            # Streamlit needs a rerun to initialize cookies
            st.stop()
        return cm
    # Fallback shim using session_state only (not persistent across browser restarts)
    class _Shim:
        def __getitem__(self, k): return st.session_state.get(f"_cookie_{k}", "")
        def __setitem__(self, k, v): st.session_state[f"_cookie_{k}"] = v
        def get(self, k, default=""): return st.session_state.get(f"_cookie_{k}", default)
        def save(self): pass
    return _Shim()

# ==========================================================
# AUTH
# ==========================================================
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
    os.makedirs(p, exist_ok=True)
    return p

def _user_paths(username: str) -> Dict[str, str]:
    base = auth_user_dir(username)
    return {
        "progress": os.path.join(base, "progress.json"),
        "history":  os.path.join(base, "history.json"),
        "sr":       os.path.join(base, "sr.json"),
    }

def persist_login(username: str, remember_days: int = 7):
    """Persist via cookie if available; else via URL param; else session-only."""
    st.session_state.auth_user = username
    token = issue_auth_token(username, remember_days)
    try:
        cm = _cookies()
        cm["auth"] = token
        cm.save()
    except Exception:
        # no cookie path → degrade to URL token
        _set_query_params(t=token)

def clear_persisted_login():
    st.session_state.pop("auth_user", None)
    try:
        cm = _cookies()
        cm["auth"] = ""
        cm.save()
    except Exception:
        _set_query_params(t=None)

def try_auto_login_persisted():
    """Restore login from cookie if available, else from URL token."""
    if st.session_state.get("auth_user"):
        return
    # Try cookie
    try:
        cm = _cookies()
        token = cm.get("auth")
        user = verify_auth_token(token) if token else None
        if user:
            st.session_state.auth_user = user
            return
    except Exception:
        pass
    # Try URL
    token = _get_query_params().get("t")
    user = verify_auth_token(token) if token else None
    if user:
        st.session_state.auth_user = user

def auth_login_form():
    st.markdown("<div class='psite-card'><b>Login</b></div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Sign in", "Create account"])

    with tab1:
        with st.form("login_form", clear_on_submit=False):
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
        with st.form("create_form", clear_on_submit=False):
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
        clear_persisted_login()
        st.rerun()

# ==========================================================
# TOPICS
# ==========================================================
CATEGORY_TO_TOPICS = {
    "Category 1: Thoracic-Pulmonary-Airway-Chest Wall": [
        "Bronchoscopy",
        "Chest Wall Deformities: Pectus Excavatum/Carinatum, Marfan’s and Poland’s Syndromes",
        "Chylothorax",
        "Congenital Diaphragmatic Hernia",
        "Cystic Diseases of the Lung",
        "Cystic Fibrosis",
        "Cystic Pulmonary Airway Malformation",
        "Empyema",
        "Esophageal Atresia and Tracheoesophageal Fistula",
        "Esophageal Perforation",
        "Esophageal Replacement",
        "Esophageal Stenosis, Webs, Diverticuli",
        "Esophageal Stricture: Caustic Ingestion and Other Causes",
        "Esophagoscopy",
        "Eventration of the Diaphragm",
        "Gastroesophageal Reflux/Barrett's Esophagus",
        "Laryngomalacia",
        "Lobar Emphysema",
        "Mediastinal Cysts, Masses",
        "Patent Ductus Arteriosus",
        "Pneumothorax",
        "Prenatal Anomalies and Therapy",
        "Pulmonary Abscess",
        "Pulmonary Hypoplasia/Hypertension",
        "Pulmonary Sequestration",
        "Subacute Bacterial Endocarditis Prophylaxis",
        "Tracheobronchial Foreign Bodies",
        "Tracheomalacia",
        "Vascular Ring and Pulmonary Artery Sling",
    ],
    "Category 2: GI-Hepatobiliary-Abdominal Wall-Fetal": [
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
    "Category 3: Head-Neck-Endocrine-Breast-GU-Imperforate Anus-Diagnosis": [
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
    "Category 4: Trauma-Critical Care-Metabolism-Surgical Emergencies": [
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
    "Category 5: Cancer-Tumors-Spleen": [
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
FALLBACK_TOPICS: List[str] = [t for cat in CATEGORY_TO_TOPICS.values() for t in cat]
def get_topics() -> List[str]: return FALLBACK_TOPICS
def get_category_map() -> dict: return CATEGORY_TO_TOPICS

NORMALIZE_ALIASES = {
    "gallbladder disease/gallstones": "Gallbladder Disease, Gallstones",
    "ovarian and adrexal problems": "Ovarian and Adnexal Problems",
    "esophageal atresia/tracheoesophageal fistula": "Esophageal Atresia and Tracheoesophageal Fistula",
}
def normalize_subject(s: str) -> str:
    key = (s or "").strip().lower()
    return NORMALIZE_ALIASES.get(key, s)

# ==========================================================
# QUESTIONS & REVIEWS
# ==========================================================
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

def load_questions_frame() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(QUESTIONS_DIR, "*.md")))
    rows = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as h:
                raw = h.read()
            meta, body = parse_front_matter(raw)
            stem, explanation = split_stem_explanation(body)
            subj = normalize_subject(meta.get("subject", "").strip())
            rec = {
                "id": meta.get("id","").strip(),
                "subject": subj,
                "A": meta.get("A","").strip(),
                "B": meta.get("B","").strip(),
                "C": meta.get("C","").strip(),
                "D": meta.get("D","").strip(),
                "E": meta.get("E","").strip(),
                "correct": meta.get("correct","").strip().upper(),
                "stem": stem,
                "explanation": explanation,
            }
            if rec["id"] and rec["subject"] and rec["correct"]:
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

def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:100]

def resolve_review_path(topic: str) -> Optional[str]:
    slug = slugify(topic)
    exact = os.path.join(REVIEWS_DIR, f"{slug}.md")
    if os.path.exists(exact): return exact
    for p in sorted(glob.glob(os.path.join(REVIEWS_DIR, "*.md"))):
        base = os.path.splitext(os.path.basename(p))[0].lower()
        if base.startswith(slug): return p
    return None

# ==========================================================
# PER-USER STATE
# ==========================================================
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
        if k not in topics:
            data.pop(k, None)
    return data

def save_progress(d: Dict[str, Dict]): _write_json(_user_file("progress"), d)
def load_history() -> List[Dict]: return _read_json(_user_file("history"), [])
def save_history(arr: List[Dict]): _write_json(_user_file("history"), arr)

def update_topic_stats(topic: str, correct: bool):
    prog = load_progress()
    if topic not in prog:
        prog[topic] = {"completed": False, "correct": 0, "total": 0, "last_seen": None, "mastered": False}
    rec = prog[topic]
    rec["total"] += 1
    rec["correct"] += 1 if correct else 0
    rec["last_seen"] = int(time.time())
    if rec["total"] >= 5 and rec["correct"]/max(1,rec["total"]) >= 0.8:
        rec["mastered"] = True
    save_progress(prog)

def topic_accuracy(topic: str) -> float:
    prog = load_progress().get(topic, {})
    c, t = prog.get("correct",0), prog.get("total",0)
    return (c/t) if t else 0.0

def suggested_topics(k:int=6) -> List[Tuple[str,float]]:
    data = load_progress(); items=[]
    for t, rec in data.items():
        acc = rec.get("correct",0)/max(1,rec.get("total",0))
        items.append((t, acc, rec.get("total",0)))
    tried = sorted([i for i in items if i[2]>0], key=lambda x: x[1])[:k]
    untried = [i for i in items if i[2]==0][:max(0,k-len(tried))]
    return [(t,a) for (t,a,_) in tried+untried]

# ==========================================================
# SPACED REPETITION (SM-2 LITE)
# ==========================================================
def _now_day_ts() -> int:
    today = dt.date.today()
    return int(time.mktime(dt.datetime(today.year, today.month, today.day).timetuple()))

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

# ==========================================================
# STREAMLIT SESSION DEFAULTS
# ==========================================================
def ensure_session_keys():
    st.session_state.setdefault("auth_user", None)
    st.session_state.setdefault("active_topic", None)   # current topic in review
    st.session_state.setdefault("view", "topics")       # "topics" | "review" | "quiz"
    st.session_state.setdefault("quiz_mode", "normal")  # normal | spaced | weakest
    st.session_state.setdefault("quiz_pool", None)
    st.session_state.setdefault("quiz_idx", 0)
    st.session_state.setdefault("quiz_answers", {})
    st.session_state.setdefault("quiz_revealed", set())
    st.session_state.setdefault("quiz_finished", False)
