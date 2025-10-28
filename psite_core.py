import os, re, glob, json, time
from typing import Dict, List, Tuple, Optional
import pandas as pd
import streamlit as st

# ---------------- Paths & setup ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
QUESTIONS_DIR = os.path.join(DATA_DIR, "questions")
REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")
STATE_DIR = os.path.join(DATA_DIR, "state")
PROGRESS_JSON = os.path.join(STATE_DIR, "progress.json")
HISTORY_JSON = os.path.join(STATE_DIR, "history.json")
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

# ---------------- Progress & history ----------------
def _read_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def _write_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_progress() -> Dict[str, Dict]:
    topics = get_topics()
    data = _read_json(PROGRESS_JSON, {})
    for t in topics:
        data.setdefault(t, {"completed": False, "correct": 0, "total": 0, "last_seen": None, "mastered": False})
    return data

def save_progress(d: Dict[str, Dict]):
    _write_json(PROGRESS_JSON, d)

def load_history() -> List[Dict]:
    return _read_json(HISTORY_JSON, [])

def save_history(arr: List[Dict]):
    _write_json(HISTORY_JSON, arr)

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

# ---------------- Session keys ----------------
def ensure_session_keys():
    st.session_state.setdefault("active_topic", None)
    st.session_state.setdefault("quiz_pool", None)   # pd.DataFrame
    st.session_state.setdefault("quiz_idx", 0)
    st.session_state.setdefault("quiz_answers", {})  # id -> chosen letter
    st.session_state.setdefault("quiz_revealed", set())
    st.session_state.setdefault("quiz_finished", False)
