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

def get_topics() -> List[str]: return ALL_TOPICS
def get_category_map() -> dict: return CATEGORY_TO_TOPICS

def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:120]

TOPIC_TO_SLUG = {t: slugify(t) for t in ALL_TOPICS}
SLUG_TO_TOPIC = {v: k for k, v in TOPIC_TO_SLUG.items()}

def topic_to_slug(t): return TOPIC_TO_SLUG.get(t, slugify(t))
def slug_to_topic(s): return SLUG_TO_TOPIC.get(s)

# ------------------------------------------------------------------ #
# QUESTION LOADING (no UI, pure pandas)
# ------------------------------------------------------------------ #
FRONT_RE = re.compile(r"^---\s*([\s\S]*?)\s*---\s*([\s\S]*)$", re.M)
EXPL_RE  = re.compile(r"<!--\s*EXPLANATION\s*-->", re.I)

def _parse_md(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        m = FRONT_RE.match(raw)
        if not m:
            return None
        fm, body = m.group(1), m.group(2)
        meta = {k.strip(): v.strip() for ln in fm.splitlines() if ":" in ln for k, v in [ln.split(":", 1)]}
        stem, expl = EXPL_RE.split(body, 1) if EXPL_RE.search(body) else (body.strip(), "")
        subject = meta.get("subject") or slug_to_topic(os.path.basename(os.path.dirname(path)))
        if not subject or subject not in ALL_TOPICS:
            return None
        return {
            "id": meta.get("id", "").strip(),
            "subject": subject,
            "stem": stem.strip(),
            "explanation": expl.strip(),
            "A": meta.get("A", "").strip(),
            "B": meta.get("B", "").strip(),
            "C": meta.get("C", "").strip(),
            "D": meta.get("D", "").strip(),
            "E": meta.get("E", "").strip(),
            "correct": meta.get("correct", "").strip().upper(),
        }
    except Exception:
        return None

def load_questions_frame() -> pd.DataFrame:
    rows = [r for p in glob.glob(os.path.join(QUESTIONS_DIR, "**", "*.md"), recursive=True) if (r := _parse_md(p))]
    if not rows:
        return pd.DataFrame(columns=["id","subject","stem","A","B","C","D","E","correct","explanation"])
    df = pd.DataFrame(rows)
    df = df[df["id"] != ""].drop_duplicates(subset="id").reset_index(drop=True)
    return df

# ------------------------------------------------------------------ #
# REVIEW HELPERS
# ------------------------------------------------------------------ #
def resolve_review_path(topic: str) -> Optional[str]:
    slug = topic_to_slug(topic)
    for cand in [f"{slug}.md", f"{topic}.md"]:
        p = os.path.join(REVIEWS_DIR, cand)
        if os.path.exists(p):
            return p
    return None

def get_review_word_count(topic: str) -> int:
    p = resolve_review_path(topic)
    if not p:
        return 0
    txt = open(p, "r", encoding="utf-8").read()
    txt = re.sub(r"```[\s\S]*?```", " ", txt)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return len(re.findall(r"[A-Za-z0-9’']+", txt))

def questions_count_by_topic() -> Dict[str, int]:
    df = load_questions_frame()
    if df.empty: return {t:0 for t in get_topics()}
    counts = df.groupby("subject")["id"].nunique().to_dict()
    for t in get_topics():
        counts.setdefault(t, 0)
    return counts

# ------------------------------------------------------------------ #
# USER STATE / ANALYTICS
# ------------------------------------------------------------------ #
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

def _user_file(key: str) -> str:
    u = st.session_state.get("auth_user")
    if not u: raise RuntimeError("Not authenticated.")
    base = os.path.join(STATE_DIR, "users", re.sub(r"[^A-Za-z0-9_.-]+", "_", u))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{key}.json")

def load_progress() -> Dict[str, dict]:
    data = _read_json(_user_file("progress"), {})
    for t in get_topics():
        data.setdefault(t, {"total":0,"correct":0,"last_seen":None})
    return data

def save_progress(d): _write_json(_user_file("progress"), d)

def load_history() -> List[Dict]:
    return _read_json(_user_file("history"), [])

def save_history(arr: List[Dict]):
    _write_json(_user_file("history"), arr)

def record_attempt(topic: str, qid: str, correct: bool):
    hist = load_history()
    hist.append({"ts": int(time.time()), "topic": topic, "id": qid, "correct": bool(correct)})
    save_history(hist)
    prog = load_progress()
    rec = prog.get(topic, {"total":0,"correct":0,"last_seen":None})
    rec["total"] += 1
    if correct: rec["correct"] += 1
    rec["last_seen"] = int(time.time())
    save_progress(prog)

def overall_accuracy() -> float:
    prog = load_progress()
    tot = sum(v.get("total",0) for v in prog.values())
    cor = sum(v.get("correct",0) for v in prog.values())
    return (cor / tot) if tot else 0.0

# ------------------------------------------------------------------ #
# SPACED REPETITION (SM-2 lite)
# ------------------------------------------------------------------ #
def _now_day_ts() -> int:
    today = dt.date.today()
    return int(time.mktime(dt.datetime(today.year,today.month,today.day).timetuple()))

def load_sr() -> Dict[str, Dict]:
    return _read_json(_user_file("sr"), {})

def save_sr(srobj: Dict[str, Dict]):
    _write_json(_user_file("sr"), srobj)

def sr_due_ids(limit:int=20, subjects: Optional[List[str]]=None) -> List[str]:
    df = load_questions_frame()
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
    sr = load_sr()
    if qid not in sr:
        sr[qid] = {"reps": 0, "interval": 0.0, "ease": 2.5, "due_ts": _now_day_ts(), "last_result": None}
    rec = sr[qid]
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
    sr[qid]=rec
    save_sr(sr)

# ------------------------------------------------------------------ #
# SESSION DEFAULTS
# ------------------------------------------------------------------ #
def ensure_session_keys():
    defaults = {
        "auth_user": None,
        "view": "dashboard",
        "active_topic": None,
        "quiz_mode": "normal",
        "quiz_pool": None,
        "quiz_idx": 0,
        "quiz_answers": {},
        "quiz_revealed": set(),
        "quiz_finished": False,
        "rail_open": True,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

# ------------------------------------------------------------------ #
# ORDERED TOPICS FOR LEARNING PATH (optimal order)
# ------------------------------------------------------------------ #
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

# ------------------------------------------------------------------ #
# 8. LAYOUT – fixed header + sidebar
# ------------------------------------------------------------------ #
st.markdown(
    "<div class='app-header'>"
    "<div class='logo'>PSITE <span>Mastery</span></div>"
    "<div></div>"   # placeholder for future icons
    "</div>",
    unsafe_allow_html=True,
)

# Sidebar navigation
nav = {
    "Dashboard": "dashboard",
    "Score Topics": "topics",
    "Make Quiz": "make_quiz",
    "Learning Path": "learning_path",
}
for label, view in nav.items():
    if st.sidebar.button(label, key=f"nav_{view}", use_container_width=True):
        st.session_state.view = view
        st.rerun()

st.sidebar.markdown("<div class='sidebar-sep'></div>", unsafe_allow_html=True)

if st.sidebar.button("Spaced Repetition", key="nav_sr", use_container_width=True):
    ids = sr_due_ids(limit=50)
    pool = ALL_Q[ALL_Q["id"].isin(ids)].reset_index(drop=True) if not ALL_Q.empty else ALL_Q
    _start_quiz(pool, mode="spaced")

st.sidebar.markdown("<div class='sidebar-sep'></div>", unsafe_allow_html=True)
if st.sidebar.button("Logout", type="secondary", use_container_width=True):
    clear_persisted_login()
    st.rerun()

# ---------- MAIN ----------
st.markdown("<div class='main'>", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# 9. VIEW ROUTER
# ------------------------------------------------------------------ #
view = st.session_state.get("view", "dashboard")

# ---------- DASHBOARD ----------
if view == "dashboard":
    st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
    attempted_all = sum(v.get("total", 0) for v in PROGRESS.values())
    total_all = sum(Q_COUNT.get(t, 0) for t in Q_COUNT)
    pct_done = _pct(attempted_all, total_all)
    pct_acc  = int(round(overall_accuracy() * 100))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-ring" style="--val:{pct_done};"><div>{pct_done}%</div></div>
              <div style="display:flex;flex-direction:column;gap:2px;">
                <div style="font-weight:600;font-size:.95rem;">Completed</div>
                <div style="font-size:.82rem;color:#6b7280">{attempted_all} of {total_all}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-ring" style="--val:{pct_acc};"><div>{pct_acc}%</div></div>
              <div style="display:flex;flex-direction:column;gap:2px;">
                <div style="font-weight:600;font-size:.95rem;">Accuracy</div>
                <div style="font-size:.82rem;color:#6b7280">All attempts</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------- TOPICS ----------
elif view == "topics":
    st.markdown("<div class='section-title'>Score Topics</div>", unsafe_allow_html=True)

    cats = get_category_map()
    s1, s2 = st.columns([2, 1])
    with s1:
        q = st.text_input("Search topics", placeholder="Search…", label_visibility="collapsed").strip().lower()
    with s2:
        cat_names = ["All"] + list(cats.keys())
        chosen_cat = st.selectbox("Category", cat_names, index=0, label_visibility="collapsed")

    topics = []
    for cat, arr in cats.items():
        if chosen_cat != "All" and cat != chosen_cat:
            continue
        for t in arr:
            if q and q not in t.lower():
                continue
            topics.append(t)

    if not topics:
        st.info("No topics match your filter.")
    else:
        cols = st.columns(3)
        for i, t in enumerate(topics):
            with cols[i % 3]:
                _render_topic_card(t)

# ---------- REVIEW ----------
elif view == "review":
    topic = st.session_state.get("active_topic")
    if not topic:
        st.info("Choose a topic from Score Topics.")
    else:
        st.markdown(f"<div class='section-title'>{topic}</div>", unsafe_allow_html=True)
        p = resolve_review_path(topic)
        if not p:
            st.info("No review uploaded yet. Place a `.md` file in `data/reviews/` named with the topic slug.")
        else:
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

# ---------- MAKE QUIZ ----------
elif view == "make_quiz":
    st.markdown("<div class='section-title'>Make a Quiz</div>", unsafe_allow_html=True)
    topics = ["Any"] + get_topics()
    pick = st.multiselect("Choose topics (or leave empty for Any):", topics, default=[])
    n = st.number_input("Number of questions", 5, 100, 20, step=5)
    if st.button("Start ▶", use_container_width=True):
        if pick and "Any" in pick:
            pick = []
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
