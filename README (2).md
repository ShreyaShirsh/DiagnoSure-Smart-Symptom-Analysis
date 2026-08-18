# DiagnoSure — AI Symptom Insights

DiagnoSure is a health assistant I built that lets you describe how you're feeling in plain language — something like *"high fever, pain behind my eyes, joint pain and a rash"* — and gives you back the conditions that most likely match, along with how serious they might be, what precautions to take, and a diet to follow.

It started as a frontend with no real brain behind it: the app looked complete, but there was no actual logic deciding what condition your symptoms pointed to. The bulk of this project was building that missing piece — a symptom-analysis engine that reasons about meaning rather than just matching keywords.

A quick, honest note first: this is a learning project, not a medical tool. It works off a fixed set of common conditions and is meant to give you *information*, not a diagnosis. Anything it suggests should be checked with an actual doctor.

## What it does

You can create an account, add family members, and run a symptom assessment for yourself or any of them. Each assessment gives you a ranked shortlist of possible conditions with a match percentage, a Low/Moderate/High risk level, specific precautions, and a diet plan. Everything gets saved to a history you can revisit, and you can download any result as a PDF report.

The part I'm most proud of is that the results are *explainable*. It doesn't just say "Dengue, 90%" — it also tells you exactly which of your symptoms led it there, so the answer never feels like a black box.

## How the symptom engine actually works

This is the interesting part, so it's worth explaining properly.

Every condition in the knowledge base has a written description of its symptoms. When you type in how you feel, the engine converts your text into a numerical vector and searches a FAISS index to find the conditions whose symptom profiles sit closest to yours. The key word is *closest in meaning* — because it compares meaning rather than exact words, "peeing a lot" can still line up with "frequent urination" even though they share no words. And it checks your symptoms against every condition it knows, then ranks them, rather than stopping at the first thing it finds.

Raw similarity alone can be a bit shaky on short text, so the final score mixes two things: how semantically close the match is, and how many of the condition's actual symptoms literally show up in what you wrote. Blending those two gives a result that's both smart about synonyms and grounded in concrete matches — and it's the "concrete matches" half that lets the app show you *why* it picked what it did.

One thing worth being clear about: the match percentage is a *relative* confidence between the top few candidates, not a real medical probability. A 90% means that condition clearly stood out from the others, not that there's a 90% chance you have it.

Finally, it works out a risk level. It starts from how serious the condition tends to be and then bumps it up based on how severe you said things were, how long they've lasted, and whether you mentioned any genuine warning signs — like bleeding gums — that shouldn't be ignored.

There's also an optional layer that can use a language model (through LangChain) to rewrite the explanation into warmer, more natural wording — but it only ever speaks from the facts the engine already retrieved, and it's switched off by default, so the app runs completely on its own without it.

If you'd like the short version to explain to someone: *it embeds a set of known conditions into a searchable index, finds the ones closest in meaning to your described symptoms, ranks them in a way you can actually inspect, and grades the risk based on severity, duration and warning signs.*

## Tech behind it

The backend is Python with Django and Django REST Framework. The symptom engine uses FAISS for the search, with sentence-transformers for the semantic embeddings when available (and a lighter scikit-learn TF-IDF approach as a fallback so it runs anywhere without a big download). LangChain powers the optional explanation layer. The frontend is plain HTML, CSS and JavaScript, with jsPDF handling report downloads, and data lives in SQLite during development.

## Getting it running

You'll need Python 3.11 or newer. On Windows, Anaconda works nicely.

First, set up the environment and install everything:

```
cd diagnosure_backend
conda create -n diagnosure python=3.11 -y
conda activate diagnosure
pip install -r requirements.txt
```

Then start the backend in one terminal:

```
python manage.py migrate
python manage.py runserver
```

That runs the API at `http://127.0.0.1:8000`. Leave it running, open a second terminal, and serve the frontend:

```
cd frontend
python -m http.server 5500
```

Now go to `http://127.0.0.1:5500/login.html` in your browser, register, log in, and try an assessment. One small thing to watch: open the frontend through that `http://` address rather than double-clicking the HTML file, otherwise the page can't reach the API.

If you want sharper synonym handling, `pip install sentence-transformers` and the engine picks it up automatically. And if you want the language-model explanation layer, install a LangChain provider, set `DIAGNOSURE_USE_LLM=1`, and add your API key — but it's genuinely optional.

## The endpoints

- `POST /api/user/` — register a new account
- `POST /api/login/` — log in
- `POST /api/analyze/` — the main one; runs the symptom engine
- `GET /api/reports/<user_id>/` — a user's saved assessments
- `GET`, `POST`, `DELETE /api/family/` — manage family members

An analyze request takes your symptoms plus optional severity, duration and medical history, and returns a ranked list where the first item is the strongest match — with the disease, score, risk, description, precautions, diet, and the symptoms that matched.

## Adding more conditions

The whole knowledge base lives in one JSON file (`api/engine/knowledge_base.json`). To teach it a new condition, add an entry with its symptoms, description, precautions, diet and so on, then restart the server — the search index rebuilds itself on startup. No code to touch.

## What I'd do next

A few things are on my list: moving the login over to proper JWT-based authentication, adding a "find nearby healthcare centres" feature based on the specialist each result recommends, saving the embeddings to disk so startup is quicker, and growing the knowledge base with more conditions.

---

Built as a learning project. Whatever it suggests, please check with a real doctor.
