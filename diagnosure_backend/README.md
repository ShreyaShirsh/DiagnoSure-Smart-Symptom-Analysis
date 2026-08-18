# DiagnoSure — Backend (Disease Determination Engine)

This is the missing "brain" of DiagnoSure. Your uploaded project was a complete
frontend that expected a Django REST backend at `http://127.0.0.1:8000`, but the
backend — and specifically the disease-determination logic — was never built.
This package supplies it.

The core of the system is a **Retrieval-Augmented Generation (RAG)** pipeline
that turns a free-text symptom description into a ranked list of likely
conditions, each with a confidence score, a risk level, precautions, and diet
advice.

---

## Why this is "strong logic" and not keyword matching

The engine (`api/engine/rag_engine.py`) works in three stages:

1. **Semantic retrieval (FAISS).**
   Every disease in the knowledge base has a canonical symptom description.
   These are embedded into vectors and stored in a **FAISS** index. At query
   time the patient's free text is embedded the same way, and FAISS returns the
   nearest diseases by cosine similarity. Because this is semantic, "pain behind
   my eyes with a rash" retrieves *Dengue* even though the wording differs from
   the stored text.

2. **Hybrid re-ranking.**
   Pure vector similarity is noisy on short text, so the final score blends
   semantic similarity (understands paraphrases) with **symptom overlap** (how
   many of the disease's concrete symptoms actually appear). Overlap makes each
   result *explainable* — the API returns `matched_symptoms` so you can show the
   patient *why* a condition was suggested.

3. **Risk stratification.**
   The disease's base risk is escalated using the reported **severity**,
   symptom **duration**, and any matched **red-flag** symptoms (e.g. "bleeding
   gums"). Red flags are matched strictly so a warning never fires on a filler
   word. The result is a clinically meaningful `Low` / `Moderate` / `High` label,
   not just a disease name.

An optional fourth stage (`api/engine/llm_explainer.py`) uses **LangChain** + an
LLM to rewrite the retrieved facts into a warmer explanation, grounded only in
the retrieved context (the "generation" in RAG). It is fully optional and
disabled by default.

### One-line summary for a viva / interview
> "DiagnoSure embeds a curated disease knowledge base into a FAISS vector index,
> retrieves candidate conditions by semantic similarity to the patient's
> free-text symptoms, re-ranks them with an explainable symptom-overlap score,
> and stratifies risk using severity, duration and red-flag detection. LangChain
> optionally generates a grounded natural-language explanation on top."

---

## Embedding backends

The retriever uses a real sentence-transformer model when available and
otherwise falls back to TF-IDF. **Either way FAISS is the vector index**, so the
architecture is identical.

| Backend | When used | Quality | Cost |
|---|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | if the library is installed | best (handles synonyms) | larger download (torch) |
| TF-IDF (scikit-learn) | default fallback | good, lexical | tiny, no download |

The MiniLM backend is better at synonyms (e.g. matching "peeing a lot" to
"frequent urination"), which the lexical TF-IDF fallback can miss.

---

## Setup

```bash
cd diagnosure_backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver        # serves http://127.0.0.1:8000
```

Then open the frontend. The simplest way is a second terminal:

```bash
cd diagnosure_backend/frontend
python -m http.server 5500        # open http://127.0.0.1:5500/login.html
```

Register a user, log in, and run an assessment.

### Optional: better embeddings
```bash
pip install sentence-transformers
```
(Nothing else to change — the engine detects and uses it automatically.)

### Optional: LLM explanation (LangChain RAG)
```bash
pip install langchain-core langchain-anthropic   # or langchain-openai
export DIAGNOSURE_USE_LLM=1
export ANTHROPIC_API_KEY=sk-...                   # or OPENAI_API_KEY
```

---

## Configuration flags (environment variables)

| Variable | Effect |
|---|---|
| `DIAGNOSURE_FORCE_TFIDF=1` | Force the TF-IDF backend even if sentence-transformers is installed |
| `DIAGNOSURE_USE_LLM=1` | Enable the LangChain explanation layer |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Provider key for the LLM layer |
| `DIAGNOSURE_SECRET_KEY` | Django secret key (set in production) |
| `DIAGNOSURE_DEBUG=0` | Turn off debug mode |

---

## API reference

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/user/` | Register `{name, email, password, age, gender}` |
| POST | `/api/login/` | Authenticate `{email, password}` → `{user: {...}}` |
| POST | `/api/analyze/` | Disease determination (see below) |
| GET | `/api/reports/<user_id>/` | List saved reports (history + diet pages) |
| GET | `/api/family/?user_id=<id>` | List family members |
| POST | `/api/family/` | Add `{user, name, relation, age}` |
| DELETE | `/api/family/` | Remove `{member_id}` |

### `POST /api/analyze/`
Request:
```json
{
  "user_id": 1,
  "symptoms": "high fever, pain behind my eyes, joint pain and a rash",
  "severity": "severe",
  "duration": "4-7days",
  "medical_history": "None",
  "patient_name": "Shreya"
}
```
Response (array; the frontend reads element `[0]` as the primary match):
```json
[{
  "disease": "Dengue Fever",
  "score": 90.2,
  "risk": "High",
  "description": "...",
  "precautions": ["..."],
  "diet": "...",
  "specialist": "General Physician / Infectious Disease",
  "matched_symptoms": ["high fever", "pain behind eyes", "joint pain", "skin rash"],
  "red_flags_detected": [],
  "semantic_similarity": 0.86,
  "symptom_overlap": 0.63
}]
```

---

## Extending the knowledge base

Add a new object to `api/engine/knowledge_base.json` with `disease`,
`specialist`, `base_risk`, `symptoms`, `symptom_text`, `red_flags`,
`description`, `precautions`, and `diet`. Restart the server — the FAISS index is
rebuilt on startup. No code changes needed. The current base ships with 25 common
conditions.

---

## Honest limitations (worth stating rather than hiding)

- **Not a medical device.** It ranks a fixed knowledge base; it does not
  diagnose. Every result should defer to a qualified doctor, and the UI says so.
- **Knowledge-base bound.** It can only suggest conditions present in the JSON.
- **The TF-IDF fallback is lexical**, so install `sentence-transformers` for the
  synonym-aware behaviour described above.

### Natural next steps
- Swap the custom `AppUser` for Django auth + JWT (`djangorestframework-simplejwt`)
  to match the "JWT" claim on your resume with real token auth.
- Add the "nearby healthcare centres" feature with a maps/places API keyed off
  the returned `specialist` field.
- Persist embeddings to disk so startup skips re-encoding.
