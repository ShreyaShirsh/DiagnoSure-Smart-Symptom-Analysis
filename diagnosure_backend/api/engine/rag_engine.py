"""
DiagnoSure RAG Engine
=====================

The disease-determination "brain" of DiagnoSure. It turns a free-text symptom
description into a ranked list of likely conditions with a confidence score,
risk level, precautions and diet advice.

Design (why it is "strong logic" and not keyword matching)
----------------------------------------------------------
1. RETRIEVAL (semantic search):
   Every disease in the knowledge base has a canonical symptom description.
   These are embedded into vectors and stored in a FAISS index. At query time
   the user's free text is embedded the same way and FAISS returns the nearest
   diseases by cosine similarity. This means "pain behind my eyes with a rash"
   matches Dengue even though the exact words differ from the KB.

2. RE-RANKING (hybrid score):
   Pure vector similarity can be noisy on short text, so the final score is a
   weighted blend of:
     - semantic similarity  (understands paraphrases / synonyms)
     - symptom overlap      (rewards concrete matched symptoms, explainable)

3. RISK STRATIFICATION:
   The disease's base risk is escalated using the reported severity, symptom
   duration and any matched red-flag symptoms (e.g. "bleeding gums"), so the
   output is clinically meaningful, not just a label.

Embedding backend
-----------------
The engine tries to use a real sentence-transformer model (MiniLM) for true
semantic embeddings. If that library is not installed, it transparently falls
back to a TF-IDF vectoriser. Either way, FAISS is the vector index, so the
architecture (semantic retrieval + FAISS) is identical.
"""

import os
import json
import re
import threading

import numpy as np
import faiss

_KB_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.json")

# Blend weights for the hybrid re-ranker (must sum to 1.0)
_W_SEMANTIC = 0.65
_W_OVERLAP = 0.35


# ----------------------------------------------------------------------------
# Embedding backends
# ----------------------------------------------------------------------------
class _SentenceTransformerBackend:
    """Real semantic embeddings via sentence-transformers (MiniLM)."""

    name = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def fit(self, corpus):
        # Nothing to fit; the model is pretrained.
        pass

    def encode(self, texts):
        vecs = self.model.encode(list(texts), convert_to_numpy=True)
        return np.asarray(vecs, dtype="float32")


class _TfidfBackend:
    """Lightweight fallback: TF-IDF vectors. No large model download needed."""

    name = "tfidf-fallback"

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), min_df=1, stop_words="english"
        )
        self._fitted = False

    def fit(self, corpus):
        self.vectorizer.fit(corpus)
        self._fitted = True

    def encode(self, texts):
        if not self._fitted:
            raise RuntimeError("TF-IDF backend must be fit() before encode().")
        mat = self.vectorizer.transform(list(texts)).toarray()
        return np.asarray(mat, dtype="float32")


def _build_backend():
    """Prefer real embeddings; fall back to TF-IDF if unavailable."""
    if os.environ.get("DIAGNOSURE_FORCE_TFIDF") == "1":
        return _TfidfBackend()
    try:
        return _SentenceTransformerBackend()
    except Exception:
        return _TfidfBackend()


# ----------------------------------------------------------------------------
# Text / symptom utilities
# ----------------------------------------------------------------------------
def _normalise(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenise(text):
    return set(_normalise(text).split())


# Filler / positional words that must not, on their own, count as a symptom or
# red-flag match (they caused "weakness on one side" to match "...on one side").
_PHRASE_STOPWORDS = {
    "a", "an", "the", "of", "on", "in", "at", "to", "and", "or", "with",
    "both", "one", "two", "side", "sides", "life", "for", "my", "your",
    "is", "are", "when", "very", "some", "any", "feeling", "sensation",
}


def _content_tokens(phrase):
    """Meaningful tokens of a phrase: drop stopwords and 1-2 char noise."""
    return {t for t in _tokenise(phrase)
            if t not in _PHRASE_STOPWORDS and len(t) >= 3}


def _phrase_matches(phrase, query_tokens, strict=False):
    """Decide whether a phrase is present in the query tokens.

    strict=False (symptoms): at least half of the content tokens must appear,
    so 'rash' matches 'skin rash' -- good recall for ranking.
    strict=True (red flags): every content token must appear, so a critical
    warning like 'blood in urine' does not fire on 'urine' alone -- high
    precision, because red flags escalate the risk level."""
    content = _content_tokens(phrase)
    if not content:
        return False
    hits = len(content & query_tokens)
    if strict:
        return hits == len(content)
    return hits >= max(1, (len(content) + 1) // 2)


class DiagnosisEngine:
    """Loads the KB once, builds the FAISS index, and answers queries."""

    def __init__(self, kb_path=_KB_PATH):
        with open(kb_path, "r", encoding="utf-8") as f:
            self.kb = json.load(f)

        self.backend = _build_backend()

        # Corpus = one canonical symptom string per disease.
        corpus = [d["symptom_text"] for d in self.kb]
        self.backend.fit(corpus)

        matrix = self.backend.encode(corpus)
        faiss.normalize_L2(matrix)  # cosine similarity via inner product
        self.index = faiss.IndexFlatIP(matrix.shape[1])
        self.index.add(matrix)

    # -- scoring helpers ----------------------------------------------------
    def _symptom_overlap(self, query_tokens, disease_idx):
        """Fraction of the disease's symptom phrases matched in the query,
        plus the list of matched phrases (used to explain the result)."""
        symptoms = self.kb[disease_idx]["symptoms"]
        if not symptoms:
            return 0.0, []
        matched_phrases = [s for s in symptoms if _phrase_matches(s, query_tokens)]
        return len(matched_phrases) / len(symptoms), matched_phrases

    def _risk_level(self, disease, severity, duration, matched_red_flags):
        """Escalate base risk using severity, duration and red-flag symptoms."""
        order = {"low": 0, "moderate": 1, "high": 2}
        label = {0: "Low", 1: "Moderate", 2: "High"}
        score = order.get(disease.get("base_risk", "low"), 0)

        if severity == "severe":
            score += 1
        elif severity == "moderate":
            score += 0  # neutral

        # Long-lasting symptoms are more concerning.
        if duration in ("1-2weeks", "more-2weeks"):
            score += 1

        # Any matched red flag pushes toward high risk immediately.
        if matched_red_flags:
            score = max(score, 2)

        score = max(0, min(2, score))
        return label[score]

    # -- public API ---------------------------------------------------------
    def diagnose(self, symptoms_text, severity=None, duration=None,
                 medical_history=None, top_k=3):
        """Return a ranked list of candidate diagnoses.

        Parameters
        ----------
        symptoms_text : str   free-text description of symptoms
        severity      : str   'mild' | 'moderate' | 'severe' (optional)
        duration      : str   duration bucket from the form (optional)
        medical_history : str  existing conditions (optional, used for notes)
        top_k         : int   number of candidates to return
        """
        query = _normalise(symptoms_text)
        if not query:
            return []

        query_tokens = _tokenise(symptoms_text)

        # 1) Semantic retrieval over the whole KB.
        q_vec = self.backend.encode([query])
        faiss.normalize_L2(q_vec)
        sims, idxs = self.index.search(q_vec, len(self.kb))
        sims, idxs = sims[0], idxs[0]

        # 2) Hybrid re-rank.
        candidates = []
        for sim, idx in zip(sims, idxs):
            disease = self.kb[idx]
            sim = max(0.0, float(sim))  # clamp tiny negatives
            overlap, matched_phrases = self._symptom_overlap(query_tokens, idx)
            blended = _W_SEMANTIC * sim + _W_OVERLAP * overlap

            matched_red_flags = [
                rf for rf in disease.get("red_flags", [])
                if _phrase_matches(rf, query_tokens, strict=True)
            ]

            candidates.append({
                "idx": int(idx),
                "disease": disease["disease"],
                "semantic": round(sim, 4),
                "overlap": round(overlap, 4),
                "_blended": blended,
                "matched_symptoms": matched_phrases,
                "matched_red_flags": matched_red_flags,
            })

        candidates.sort(key=lambda c: c["_blended"], reverse=True)
        top = candidates[:top_k]
        if not top:
            return []

        # 3) Normalise blended scores into a friendly 0-100 confidence.
        #    Softmax-style relative confidence across the top candidates so the
        #    best match gets a high number and near-ties stay close together.
        blends = np.array([c["_blended"] for c in top], dtype="float64")
        if blends.max() <= 0:
            return []
        exp = np.exp((blends - blends.max()) * 6.0)
        confidence = exp / exp.sum()

        results = []
        for c, conf in zip(top, confidence):
            disease = self.kb[c["idx"]]
            risk = self._risk_level(
                disease, severity, duration, c["matched_red_flags"]
            )
            notes = None
            if medical_history and medical_history.strip():
                notes = (
                    "You reported existing conditions ("
                    + medical_history.strip()
                    + "). Please mention these to your doctor as they may affect "
                    "diagnosis and treatment."
                )

            results.append({
                "disease": disease["disease"],
                "disease_name": disease["disease"],
                "score": round(float(conf) * 100, 1),
                "risk": risk,
                "description": disease["description"],
                "precautions": disease["precautions"],
                "diet": disease["diet"],
                "specialist": disease["specialist"],
                "symptoms": disease["symptoms"],
                "matched_symptoms": c["matched_symptoms"],
                "red_flags_detected": c["matched_red_flags"],
                "semantic_similarity": c["semantic"],
                "symptom_overlap": c["overlap"],
                "notes": notes,
                "engine": self.backend.name,
            })
        return results


# ----------------------------------------------------------------------------
# Lazy singleton so the model / index load only once per process.
# ----------------------------------------------------------------------------
_engine = None
_lock = threading.Lock()


def get_engine():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = DiagnosisEngine()
    return _engine
