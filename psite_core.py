# psite_core.py
import os, re, glob, json, time, hashlib, hmac, base64
from typing import Dict, List, Tuple, Optional
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ============================== TOPICS ==============================
CATEGORY_TO_TOPICS = {
    "Category 1: Thoracic-Pulmonary-Airway-Chest Wall": [
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
def get_topics() -> List[str]:
    return [t for arr in CATEGORY_TO_TOPICS.values() for t in arr]
def get_category_map() -> dict:
    return CATEGORY_TO_TOPICS

# ============================== PATHS ==============================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
STATE_DIR = os.path.join(DATA_DIR, "state")
USERS_JSON = os.path.join(STATE_DIR, "users.json")  # (only needed if you use auth elsewhere)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)

# Where to look for questions (in priority order)
QUESTION_ROOTS: List[str] = []
_env_qdir = os.getenv("QBANK_QUESTIONS_DIR", "").strip()
if _env_qdir:
    QUESTION_ROOTS.append(os.path.abspath(os.path.join(BASE_DIR, _env_qdir)) if not os.path.isabs(_env_qdir) else _env_qdir)
QUESTION_ROOTS += [
    os.path.join(BASE_DIR, "data", "questions"),
    os.path.join(BASE_DIR, "pages", "data", "questions"),  # also support pages/data/questions
]
# Make sure those exist (no error if missing)
for p in QUESTION_ROOTS:
    os.makedirs(p, exist_ok=True)

# ============================== SLUG MAPS ==============================
def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()

TOPIC_TO_SLUG = {t: slugify(t) for t in get_topics()}
SLUG_TO_TOPIC = {v: k for k, v in TOPIC_TO_SLUG.items()}

# ============================== MARKDOWN PARSE ==============================
FRONTMATTER_RE = re.compile(r"^---\s*([\s\S]*?)\s*---\s*([\s\S]*)$", re.MULTILINE)
EXPL_SPLIT_RE  = re.compile(r"<!--\s*EXPLANATION\s*-->", re.IGNORECASE)
REQUIRED_COLS  = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

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
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (body.strip(), "")

def _infer_subject_from_path(path: str) -> Optional[str]:
    parent = os.path.basename(os.path.dirname(path)).lower()
    return SLUG_TO_TOPIC.get(parent)

def _discover_question_files() -> List[str]:
    files: List[str] = []
    for root in QUESTION_ROOTS:
        if not os.path.isdir(root):
            continue
        files.extend(sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True)))
    return files

def load_questions_frame() -> pd.DataFrame:
    files = _discover_question_files()
    rows = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as h:
                raw = h.read()
            meta, body = parse_front_matter(raw)
            stem, explanation = split_stem_explanation(body)
            subject = (meta.get("subject","") or "").strip() or _infer_subject_from_path(f) or ""
            rec = {
                "id": meta.get("id","").strip(),
                "subject": subject,
                "A": meta.get("A","").strip(),
                "B": meta.get("B","").strip(),
                "C": meta.get("C","").strip(),
                "D": meta.get("D","").strip(),
                "E": meta.get("E","").strip(),
                "correct": (meta.get("correct","") or "").strip().upper(),
                "stem": stem,
                "explanation": explanation,
            }
            # Accept only well-formed questions for known topics
            if rec["id"] and rec["correct"] and rec["stem"] and rec["subject"] in TOPIC_TO_SLUG:
                rows.append(rec)
        except Exception:
            # skip malformed files
            continue
    if not rows:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df = pd.DataFrame(rows)
    for c in REQUIRED_COLS:
        if c not in df.columns: df[c] = ""
        df[c] = df[c].astype(str).str.strip()
    df["correct"] = df["correct"].str.upper()
    df = df.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    return df

def load_questions_for_subjects(subjects: List[str]) -> pd.DataFrame:
    df = load_questions_frame()
    if df.empty: return df
    return df if not subjects else df[df["subject"].isin(subjects)].reset_index(drop=True)

def questions_count_by_topic() -> Dict[str, int]:
    df = load_questions_frame()
    if df.empty: return {t:0 for t in get_topics()}
    return df.groupby("subject")["id"].nunique().to_dict()

def debug_questions_index() -> pd.DataFrame:
    df = load_questions_frame()
    if df.empty:
        return pd.DataFrame({"subject": [], "questions_found": []})
    return df.groupby("subject")["id"].nunique().reset_index(name="questions_found").sort_values("subject")
