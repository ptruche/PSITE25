import os, re, glob, json, time, secrets, base64, hashlib, hmac, datetime as dt
from typing import Dict, List, Tuple, Optional
import pandas as pd
import streamlit as st

# ---------------- Paths & setup ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
QUESTIONS_DIR = os.path.join(DATA_DIR, "questions")
REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")
STATE_DIR = os.path.join(DATA_DIR, "state")
USERS_JSON = os.path.join(STATE_DIR, "users.json")
THEME_CSS = os.path.join(BASE_DIR, "theme.css")

for p in [DATA_DIR, QUESTIONS_DIR, REVIEWS_DIR, STATE_DIR]:
    os.makedirs(p, exist_ok=True)

# ---------------- Styling ----------------
def apply_base_theme():
    if os.path.exists(THEME_CSS):
        with open(THEME_CSS, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <style>
            :root { --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280; }
            .block-container { padding-top:1.05rem !important; }
            .psite-card { border:1px solid var(--card-border); border-radius:12px; background:#fff; padding:12px; }
            .psite-title { font-weight:700; font-size:1.1rem; }
            .grid-3 { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; }
            </style>
            """,
            unsafe_allow_html=True,
        )

# ---------------- Auth (local, PBKDF2) ----------------
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
    p = os.path.join(STATE_DIR, "users", re.sub(r"[^A-Za-z0-9_.-]+","_", username))
    os.makedirs(p, exist_ok=True)
    return p

def _user_paths(username: str) -> Dict[str, str]:
    base = auth_user_dir(username)
    return {
        "progress": os.path.join(base, "progress.json"),
        "history":  os.path.join(base, "history.json"),
        "sr":       os.path.join(base, "sr.json"),
    }

def auth_login_form():
    st.markdown("<div class='psite-title'>Login</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Sign in", "Create account"])
    with tab1:
        with st.form("login_form", clear_on_submit=False):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
            if submitted:
                users = _read_json(USERS_JSON, {})
                rec = users.get(u)
                if not rec or not _verify_pw(p, rec["salt"], rec["hash"]):
                    st.error("Invalid username or password.")
                else:
                    st.session_state.auth_user = u
                    st.success(f"Welcome back, {u}.")
                    st.experimental_rerun()
    with tab2:
        with st.form("create_form", clear_on_submit=False):
            u = st.text_input("New username")
            p1 = st.text_input("Password", type="password")
            p2 = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account")
            if submitted:
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
                        # prime per-user dirs
                        _ = auth_user_dir(u)
                        st.success("Account created. Please sign in.")
                        st.experimental_rerun()

def auth_logout_button():
    if st.button("Logout", type="secondary"):
        st.session_state.pop("auth_user", None)
        st.experimental_rerun()

# ---------------- Topic catalogue ----------------
FALLBACK_TOPICS: List[str] = [
    "Fluids/and/Electrolytes","Nutrition","Pediatric Anesthesia/and/Pain Management",
    "Neonatal Physiology/and/Pathophysiology: Transition from Fetal Circulation/Cardiovascular Monitoring/Shock",
    "Lung Physiology/Pathophysiology/Ventilators/Pneumonia","ARDS","Coagulation",
    "Neonatal Obstruction","Duodenal Atresia/Stenosis/Webs/Annular Pancreas","Intestinal Atresia","Malrotation",
    "Meconium Ileus/Peritonitis/Plug","Necrotizing Enterocolitis",
    "Gastroschisis","Omphalocele","Umbilical Hernia/and/Other Umbilical Disorders",
    "Esophageal Atresia/and/Tracheoesophageal Fistula","Esophageal Stenosis/Webs/Diverticuli",
    "Esophageal Stricture: Caustic Ingestion/and/Other Causes","Esophageal Perforation","Esophageal Replacement","Esophagoscopy",
    "Gastroesophageal Reflux/Barrett’s Esophagus","Gastric Volvulus","Peptic Ulcer Disease",
    "Congenital Diaphragmatic Hernia","Eventration of the Diaphragm","Lobar Emphysema","Cystic Pulmonary Airway Malformation",
    "Pulmonary Sequestration","Cystic Diseases of the Lung","Chylothorax","Empyema","Pneumothorax","Pulmonary Abscess",
    "Pulmonary Hypoplasia/Hypertension","Vascular Ring/and/Pulmonary Artery Sling","Tracheomalacia",
    "Tracheobronchial Foreign Bodies","Bronchoscopy","Laryngomalacia",
    "Biliary Atresia","Choledochal Cysts","Gallbladder Disease/Gallstones","Hepatic Infections: Hepatitis/Abscess/Cysts","Portal Hypertension",
    "Hirschsprung Disease","Inflammatory Bowel Disease","Short Bowel Syndrome/Intestinal Failure","Gastrointestinal Bleeding","Polyps",
    "Alimentary Tract Duplications","Mesenteric/and/Omental Cysts","Ascites: Chylous","Omphalomesenteric Duct Remnants/Urachus/and/Meckel’s",
    "Abdominal Pain","Neonatal Gastric Perforation",
    "Inguinal Hernia","Undescended Testicle (Cryptorchidism)","Torsions: Appendix Testes/Testicular",
    "Circumcision/and/Abnormalities of the Urethra/Penis/Scrotum","Disorders of Sexual Development","Ovarian Torsion/Cysts/and/Tumors",
    "Ovarian/and/Adnexal Problems","Renal Diseases: Nephrotic Syndrome/DI/Renal Vein Thrombosis/Chronic Failure/Prune Belly Syndrome",
    "Endocrine Diseases","Thyroid Nodules","Thyroglossal Duct Cyst/Sinus","Vaginal Atresia/Hydrometrocolpos",
    "Branchial Cleft/Arch Anomalies","Breast Disorders","Torticollis","Lymphadenopathy/Atypical Mycobacteria",
    "Vascular Anomalies","Dermoid/Epidermoid Cysts/Soft Tissue Nodules","Subacute Bacterial Endocarditis Prophylaxis","Patent Ductus Arteriosus",
    "Prenatal Anomalies/and/Therapy","Mediastinal Cysts/Masses",
    "Abdominal Mass/in/the/Newborn","Benign Liver Tumors: Hepatic Mesenchymal Hamartoma/Adenoma/FNH",
    "Malignant Liver Tumors: Hepatoblastoma/Hepatocellular Carcinoma","Lung/and/Chest Wall Tumors",
    "Gastrointestinal Tumors","Bone Tumors: Osteogenic Sarcoma/Ewing Sarcoma","Rhabdomyosarcoma","Neuroblastoma",
    "Wilms Tumor/Renal Cell Carcinoma/and/Hemihypertrophy","Mesoblastic Nephroma","Testicular Tumors","Lymphoma/Leukemia",
    "Nevi/Melanoma","Adrenal Cancer","Chemo/Radiation Therapy/Immunotherapy Concepts/Genetics","Splenic Diseases","Teratoma",
    "Trauma: Initial Assessment/and/Resuscitation","Thoracic Trauma","Abdominal Trauma","Musculoskeletal Trauma: Pelvis/Long Bone",
    "Cardiovascular Trauma: Tamponade/Contusion/Arch Disruption/Peripheral Vascular Injuries","Nonaccidental Injuries: Diagnosis/Evaluation/Legal Issues",
    "Burns: Resuscitation/Airway/Electrical/Nutrition/Wound/Sepsis","Extracorporeal Life Support","Acute Renal Failure","Neurosurgical Trauma",
    "Transplantation"
]

def get_topics() -> List[str]:
    return FALLBACK_TOPICS

# ---------------- Question loader ----------------
FRONTMATTER_RE = re.compile(r"^---\s*([\s\S]*?)\s*---\s*([\s\S]*)$", re.MULTILINE)
EXPL_SPLIT_RE  = re.compile(r"<!--\s*EXPLANATION\s*-->", re.IGNORECASE)
REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

def parse_front_matter(text: str) -> Tuple[Dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("Missing front-matter '--- ... ---'")
    fm, body = m.group(1), m.group(2)
    meta: Dict[str, str] = {}
    for line in fm.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body.strip()

def split_stem_explanation(body: str) -> Tuple[str, str]:
    parts = EXPL_SPLIT_RE.split(body, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return body.strip(), ""

def load_questions_frame() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(QUESTIONS_DIR, "*.md")))
    rows = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as h:
                raw = h.read()
            meta, body = parse_front_matter(raw)
            stem, explanation = split_stem_explanation(body)
            rec = {
                "id": meta.get("id","").strip(),
                "subject": meta.get("subject","").strip(),
                "A": meta.get("A","").strip(),
                "B": meta.get("B","").strip(),
                "C": meta.get("C","").strip(),
                "D": meta.get("D","").strip(),
                "E": meta.get("E","").strip(),
                "correct": meta.get("correct","").strip().upper(),
                "stem": stem,
                "explanation": explanation,
            }
            if not rec["id"] or not rec["subject"] or not rec["correct"]:
                continue
            rows.append(rec)
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df = pd.DataFrame(rows)
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str).str.strip()
    df["correct"] = df["correct"].str.upper()
    df = df.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    return df

def load_questions_for_subjects(subjects: List[str]) -> pd.DataFrame:
    if not subjects:
        return load_questions_frame()
    df = load_questions_frame()
    if df.empty:
        return df
    return df[df["subject"].isin(subjects)].reset_index(drop=True)

# ---------------- Review files ----------------
def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:100]

def resolve_review_path(topic: str) -> Optional[str]:
    slug = slugify(topic)
    exact = os.path.join(REVIEWS_DIR, f"{slug}.md")
    if os.path.exists(exact):
        return exact
    for p in sorted(glob.glob(os.path.join(REVIEWS_DIR, "*.md"))):
        base = os.path.splitext(os.path.basename(p))[0].lower()
        if base.startswith(slug):
            return p
    return None

# ---------------- Per-user progress & history ----------------
def _user_file(pathkey: str) -> str:
    u = st.session_state.get("auth_user")
    if not u:
        raise RuntimeError("Not authenticated.")
    return _user_paths(u)[pathkey]

def load_progress() -> Dict[str, Dict]:
    topics = get_topics()
    data = _read_json(_user_file("progress"), {})
    for t in topics:
        data.setdefault(t, {"completed": False, "correct": 0, "total": 0, "last_seen": None, "mastered": False})
    return data

def save_progress(d: Dict[str, Dict]):
    _write_json(_user_file("progress"), d)

def load_history() -> List[Dict]:
    return _read_json(_user_file("history"), [])

def save_history(arr: List[Dict]):
    _write_json(_user_file("history"), arr)

def update_topic_stats(topic: str, correct: bool):
    prog = load_progress()
    rec = prog.setdefault(topic, {"completed": False, "correct": 0, "total": 0, "last_seen": None, "mastered": False})
    rec["total"] += 1
    rec["correct"] += 1 if correct else 0
    rec["last_seen"] = int(time.time())
    if rec["total"] >= 5 and rec["correct"] / max(1, rec["total"]) >= 0.8:
        rec["mastered"] = True
    save_progress(prog)

def topic_accuracy(topic: str) -> float:
    prog = load_progress().get(topic, {})
    c, t = prog.get("correct", 0), prog.get("total", 0)
    return (c / t) if t else 0.0

def suggested_topics(k: int = 6) -> List[Tuple[str, float]]:
    data = load_progress()
    items = []
    for t, rec in data.items():
        acc = (rec.get("correct",0) / max(1, rec.get("total",0)))
        items.append((t, acc, rec.get("total",0)))
    tried = sorted([i for i in items if i[2] > 0], key=lambda x: x[1])[:k]
    untried = [i for i in items if i[2] == 0][:max(0, k - len(tried))]
    return [(t, a) for (t, a, _) in tried + untried]

# ---------------- Spaced Repetition (SM-2 lite) ----------------
# Per-question record: {reps, interval, ease, due_ts, last_result}
def _now_day_ts() -> int:
    # midnight today UTC (or use local; consistent is fine)
    today = dt.date.today()
    return int(time.mktime(dt.datetime(today.year, today.month, today.day).timetuple()))

def load_sr() -> Dict[str, Dict]:
    return _read_json(_user_file("sr"), {})

def save_sr(srobj: Dict[str, Dict]):
    _write_json(_user_file("sr"), srobj)

def _init_sr_if_needed(qid: str):
    sr = load_sr()
    if qid not in sr:
        sr[qid] = {"reps": 0, "interval": 0.0, "ease": 2.5, "due_ts": _now_day_ts(), "last_result": None}
        save_sr(sr)

def sr_due_ids(limit: int = 20, subjects: Optional[List[str]] = None) -> List[str]:
    df = load_questions_for_subjects(subjects or [])
    if df.empty:
        return []
    sr = load_sr()
    today = _now_day_ts()
    ids = []
    for _, r in df.iterrows():
        qid = r["id"]
        d = sr.get(qid, None)
        due_ts = d["due_ts"] if d else today
        if due_ts <= today:
            ids.append(qid)
    # If nothing due, take next-upcoming few
    if not ids:
        upcoming = sorted(
            ((q, sr.get(q, {"due_ts": today})["due_ts"]) for q in df["id"].tolist()),
            key=lambda x: x[1]
        )
        ids = [q for q, _ in upcoming[:limit]]
    return ids[:limit]

def sr_update(qid: str, was_correct: bool):
    _init_sr_if_needed(qid)
    sr = load_sr()
    rec = sr[qid]
    # Map to SM-2 style update; binary correctness -> quality
    quality = 4 if was_correct else 2  # 0..5 scale simplified
    ease = rec.get("ease", 2.5)
    reps = rec.get("reps", 0)
    interval = rec.get("interval", 0.0)

    if was_correct:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = round(interval * ease)
        reps += 1
        ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    else:
        reps = 0
        interval = 1
        ease = max(1.3, ease - 0.2)

    due_date = dt.date.today() + dt.timedelta(days=int(interval))
    due_ts = int(time.mktime(dt.datetime(due_date.year, due_date.month, due_date.day).timetuple()))
    rec.update({"reps": reps, "interval": float(interval), "ease": float(ease), "due_ts": due_ts, "last_result": int(was_correct)})
    sr[qid] = rec
    save_sr(sr)

# ---------------- Weakest topics helper ----------------
def weakest_topics(n_topics: int = 3) -> List[str]:
    data = load_progress()
    tried = [(t, v["correct"]/max(1,v["total"]), v["total"]) for t, v in data.items() if v["total"] > 0]
    if not tried:
        return get_topics()[:n_topics]
    tried_sorted = sorted(tried, key=lambda x: (x[1], x[2]))[:n_topics]
    return [t for t, _, _ in tried_sorted]

# ---------------- Session keys ----------------
def ensure_session_keys():
    st.session_state.setdefault("auth_user", None)
    st.session_state.setdefault("active_topic", None)
    st.session_state.setdefault("quiz_mode", "normal")  # normal | spaced | weakest
    st.session_state.setdefault("quiz_pool", None)   # pd.DataFrame
    st.session_state.setdefault("quiz_idx", 0)
    st.session_state.setdefault("quiz_answers", {})  # id -> chosen letter
    st.session_state.setdefault("quiz_revealed", set())
    st.session_state.setdefault("quiz_finished", False)
