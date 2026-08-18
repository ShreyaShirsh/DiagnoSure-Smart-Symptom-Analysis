"""Optional LLM "generation" layer for DiagnoSure (the G in RAG).

The retrieval engine (rag_engine.py) already returns a full, safe answer from
the curated knowledge base, so the app works with zero external dependencies.

This module OPTIONALLY uses LangChain + an LLM to rewrite the retrieved facts
into a warmer, more personalised explanation grounded ONLY in the retrieved
context (classic Retrieval-Augmented Generation). It is fully gated:

  * Disabled unless DIAGNOSURE_USE_LLM=1
  * Needs LangChain + a provider key (OPENAI_API_KEY or ANTHROPIC_API_KEY)
  * Any failure falls back silently to the knowledge-base description

Keeping the LLM grounded in retrieved context (not free-generating medical
claims) is the safety point of RAG and a good thing to explain in a viva.
"""
import os


def _llm_enabled():
    return os.environ.get("DIAGNOSURE_USE_LLM") == "1"


def _build_llm():
    """Return a LangChain chat model, or None if unavailable."""
    try:
        if os.environ.get("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
        if os.environ.get("ANTHROPIC_API_KEY"):
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model="claude-3-5-haiku-latest", temperature=0.2)
    except Exception:
        return None
    return None


_PROMPT = (
    "You are a careful medical information assistant. Using ONLY the context "
    "below, write 2-3 short sentences explaining the most likely condition to "
    "a patient in plain, reassuring language. Do NOT invent symptoms, drugs or "
    "diagnoses beyond the context. Always end by advising them to consult a "
    "qualified doctor for confirmation.\n\n"
    "Patient described: {symptoms}\n"
    "Most likely condition: {disease}\n"
    "Reference description: {description}\n"
    "Reference precautions: {precautions}\n\n"
    "Explanation:"
)


def generate_explanation(symptoms, disease, description, precautions):
    """Return an LLM-written explanation grounded in the retrieved context,
    or None to signal the caller to use the knowledge-base description."""
    if not _llm_enabled():
        return None
    llm = _build_llm()
    if llm is None:
        return None
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        chain = (
            ChatPromptTemplate.from_template(_PROMPT)
            | llm
            | StrOutputParser()
        )
        text = chain.invoke({
            "symptoms": symptoms,
            "disease": disease,
            "description": description,
            "precautions": ", ".join(precautions),
        })
        return (text or "").strip() or None
    except Exception:
        return None
