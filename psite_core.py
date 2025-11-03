# === Add/ensure these are present near your topic helpers ===
def slugify(s: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:120]

# (Assumes you already have ALL_TOPICS, TOPIC_TO_SLUG, SLUG_TO_TOPIC built from CATEGORY_TO_TOPICS)
# If not, build:
# TOPIC_TO_SLUG = {t: slugify(t) for t in ALL_TOPICS}
# SLUG_TO_TOPIC = {v: k for k, v in TOPIC_TO_SLUG.items()}

def _infer_subject_from_path(path: str) -> str | None:
    """Infer by parent folder slug."""
    import os
    parent = os.path.basename(os.path.dirname(path)).lower()
    return SLUG_TO_TOPIC.get(parent)

def normalize_subject(meta_subject: str, path: str) -> str | None:
    """
    Map any incoming 'subject' to a canonical topic:
      1) exact match,
      2) slugified match,
      3) parent folder match.
    Returns canonical topic string or None.
    """
    topics = set(get_topics())
    if meta_subject and meta_subject in topics:
        return meta_subject
    if meta_subject:
        s = slugify(meta_subject)
        if s in SLUG_TO_TOPIC:
            return SLUG_TO_TOPIC[s]
    inf = _infer_subject_from_path(path)
    if inf:
        return inf
    return None
