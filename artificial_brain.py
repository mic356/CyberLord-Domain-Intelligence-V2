"""CyberLord Artificial Brain: shared reasoning, routing and memory utilities.

This module orchestrates existing AI providers; it is not a new trained foundation
model. It builds bounded instructions and retrieves user-approved memory only.
"""
import re
from collections import Counter

_STOP = {
    "the", "and", "for", "that", "this", "with", "from", "have", "what", "when",
    "where", "which", "would", "could", "should", "about", "your", "you", "are",
    "was", "were", "will", "can", "how", "why", "who", "into", "their", "them",
    "then", "than", "there", "here", "please", "help", "want", "need"
}


def terms(text):
    return [w for w in re.findall(r"[a-z0-9_+-]{2,}", str(text or "").lower()) if w not in _STOP]


def classify_request(text):
    """Return a coarse capability route; it never executes a tool by itself."""
    q = str(text or "").lower()
    routes = []
    patterns = {
        "image_understanding": r"\b(image|picture|photo|screenshot|diagram|chart|attached)\b",
        "document_analysis": r"\b(pdf|document|docx|spreadsheet|excel|xlsx|powerpoint|pptx|file)\b",
        "video_analysis": r"\b(video|clip|footage|movie)\b",
        "audio": r"\b(audio|voice|voice note|recording|transcribe|spoken)\b",
        "web_research": r"\b(search online|search the web|latest|today|current|research|sources|look up)\b",
        "creation": r"\b(create|generate|draw|design|make me|write|build|produce)\b",
        "planning": r"\b(plan|steps|roadmap|organise|organize|schedule|strategy)\b",
    }
    for route, pattern in patterns.items():
        if re.search(pattern, q):
            routes.append(route)
    return routes or ["conversation"]


def retrieve_relevant_memories(rows, query, limit=5):
    """Rank only this user's existing memory rows by lexical relevance and recency order."""
    query_terms = set(terms(query))
    if not query_terms:
        return list(rows or [])[:limit]
    scored = []
    for index, row in enumerate(rows or []):
        summary = str(row.get("summary") or "")
        topic = str(row.get("topic") or "")
        row_terms = set(terms(summary + " " + topic))
        overlap = len(query_terms & row_terms)
        if overlap:
            scored.append((overlap / max(1, len(query_terms)), -index, row))
    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    # Include a small recent-memory tail so broad preferences remain available.
    chosen = [item[2] for item in scored[:limit]]
    for row in list(rows or []):
        if len(chosen) >= limit:
            break
        if row not in chosen and row.get("kind") in ("preference", "progress"):
            chosen.append(row)
    return chosen


def build_brain_instruction(user_text, persona="main", memory_rows=None):
    """Create a concise orchestration and self-review instruction for the shared AI."""
    routes = classify_request(user_text)
    memory = retrieve_relevant_memories(memory_rows or [], user_text)
    memory_lines = ["- " + str(row.get("summary", ""))[:350] for row in memory if row.get("summary")]
    lines = [
        "CYBERLORD ARTIFICIAL BRAIN — SHARED ORCHESTRATION LAYER",
        "You are the reasoning and orchestration layer for CyberLord. Use the connected model's capabilities; do not claim to have tools or data that were not actually supplied.",
        "Request capability signals: " + ", ".join(routes) + ". These are hints, not proof that a tool ran.",
        "Think through the task privately in ordered steps. Do not reveal hidden chain-of-thought; provide a concise explanation, key assumptions and useful steps instead.",
        "Before answering, silently check: (1) did I answer the actual request, (2) which claims are supported, (3) did I confuse inference with observed evidence, (4) are dates, numbers and names uncertain, (5) is an external action or permission required?",
        "Never invent image contents, document text, video events, citations, tool results, account state or completed actions. If input is missing, unreadable or ambiguous, say exactly what is uncertain and ask for the smallest useful clarification.",
        "For multi-part tasks, organise the response into clear deliverables and identify incomplete/provider-dependent work. For high-impact or external actions, prepare a preview and request explicit approval before acting.",
        "Use relevant approved user memory only to improve continuity. Memory may be outdated; do not treat it as proof of current account, payment, health, legal or security state.",
        "Persona boundary: " + ("CyberLord Academy Tutor; teach cybersecurity topics safely, step by step, and stay within the academy." if persona == "tutor" else "CyberLord Dashboard assistant; answer general requests naturally and redirect cybersecurity learning to the Academy Tutor."),
    ]
    if memory_lines:
        lines.append("Relevant saved user context (private to this account):\n" + "\n".join(memory_lines))
    return "\n".join(lines)


def answer_quality_flags(answer):
    """Lightweight deterministic checks for obvious uncertainty/citation issues."""
    text = str(answer or "")
    flags = []
    if not text.strip():
        flags.append("empty_answer")
    if re.search(r"\b(I searched|I checked|I scanned|I uploaded|I sent|I created)\b", text, re.I) and not re.search(r"\b(tool|source|file|result|attached|download)\b", text, re.I):
        flags.append("verify_action_claim")
    if re.search(r"\b(100% accurate|guaranteed|definitely safe|completely secure)\b", text, re.I):
        flags.append("absolute_claim_review")
    return flags
