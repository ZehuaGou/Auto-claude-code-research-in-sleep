"""Scoring, dedup, and relevance helpers — extracted from literature_evidence_landing.py."""

from __future__ import annotations

import hashlib
import re


# ---- Keyword groups for relevance scoring ----

_HALLUCINATION_GROUP = frozenset([
    "hallucination", "hallucinations", "confabulation", "factuality", "factual",
    "truthfulness", "untruthful", "misinformation", "faithfulness", "faithful",
    "hallucinate", "hallucinated", "fabrication", "inaccurate", "inaccuracy",
])

_LLM_GROUP = frozenset([
    "llm", "llms", "large language model", "language model", "foundation model",
    "generative ai", "generative model", "neural language model", "transformer",
    "chatgpt", "gpt", "bert", "llama", "mistral",
])

_INTERNAL_STATE_GROUP = frozenset([
    "hidden state", "hidden states", "internal state", "internal states",
    "activation", "activations", "representation", "representations",
    "layer", "layerwise", "trajectory", "embedding", "embeddings",
    "neural activation", "model state", "latent", "intermediate representation",
])

_TOKEN_GROUP = frozenset([
    "token", "tokens", "token-level", "per-token", "decoding step",
    "generation step", "logit", "logits", "token probability", "token uncertainty",
    "token-level detection", "word-level",
])

_DETECTION_GROUP = frozenset([
    "detect", "detection", "detector", "anomaly", "outlier", "uncertainty",
    "confidence", "estimation", "monitor", "monitoring", "identification",
    "classification", "recognition",
])

_NEGATIVE_GROUP = frozenset([
    "metaverse", "geriatric", "agriculture", "forecasting", "self-adaptive",
    "personal agents", "prompt engineering", "medical", "healthcare",
    "robotics decision-making", "autonomous systems", "sensor network",
    "smart city", "edge computing", "iot", "internet of things",
    "pharmaceutical", "supply chain", "pharmacy", "healthcare logistics",
    "medicine", "medical domain", "clinical", "education", "chatbot medical",
    "drug", "patient", "hospital", "therapeutic", "pharmacology",
])

_STRONG_DOMAIN_NEGATIVES = frozenset([
    "pharmaceutical", "supply chain", "pharmacy", "healthcare logistics",
    "medical domain", "clinical", "geriatric", "metaverse", "agriculture",
    "education", "chatbot medical", "drug discovery", "patient",
])


def _normalize_title(title: str) -> str:
    """Lowercase, trim, collapse whitespace, remove punctuation, strip subtitles."""
    t = title.lower().strip()
    t = t.split(":")[0].strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^\w\s]", "", t)
    return t.strip()


def _is_title_match(t1: str, t2: str) -> bool:
    """Check if two normalized titles are semantically the same paper."""
    if not t1 or not t2:
        return False
    if t1 == t2:
        return True
    shorter, longer = (t1, t2) if len(t1) <= len(t2) else (t2, t1)
    if len(longer) > 0 and len(shorter) / len(longer) >= 0.8:
        if longer.startswith(shorter):
            return True
    return False


def _canonical_identity(rec: dict, normalized_title: str, year: str) -> str:
    """Return a stable canonical identity string for dedup."""
    doi = rec.get("doi", "").strip()
    arxiv = rec.get("arxiv_id", "").strip()
    ss = rec.get("semantic_scholar_id", "").strip()
    oa = rec.get("openalex_id", "").strip()
    if doi:
        return f"doi:{doi.lower()}"
    if arxiv:
        return f"arxiv:{arxiv}"
    if ss:
        return f"semantic_scholar:{ss}"
    if oa:
        return f"openalex:{oa}"
    return f"title_year:{normalized_title}|{year}"


def _is_arxiv_doi(doi: str) -> bool:
    """Check if a DOI is an arXiv DOI."""
    return "arxiv" in doi.lower() or "10.48550" in doi


def _candidate_id_from_identity(identity: str) -> str:
    """Stable candidate ID from canonical identity (no raw index)."""
    h = hashlib.md5(identity.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"cand_{h}"


def _build_stable_ids(rec: dict) -> dict:
    return {
        "doi": rec.get("doi") or "",
        "arxiv_id": rec.get("arxiv_id") or "",
        "semantic_scholar_id": rec.get("semantic_scholar_id") or "",
        "openalex_id": rec.get("openalex_id") or "",
    }


def _authors_to_list(authors):
    if isinstance(authors, list):
        return authors
    if isinstance(authors, str):
        return [a.strip() for a in authors.split(",") if a.strip()]
    return []


def _score_text_relevance(title: str, abstract: str, must_include: list[str]) -> dict:
    """Deterministic keyword/concept relevance scoring. No model, no semantic inference."""
    text = f"{title} {abstract}".lower()
    score = 0
    reasons = []
    flags = []
    hallucination_hits = sum(1 for term in _HALLUCINATION_GROUP if term in text)
    if hallucination_hits > 0:
        score += 3
        reasons.append(f"hallucination_group matched ({hallucination_hits} terms)")
    llm_hits = sum(1 for term in _LLM_GROUP if term in text)
    if llm_hits > 0:
        score += 2
        reasons.append(f"llm_group matched ({llm_hits} terms)")
    internal_hits = sum(1 for term in _INTERNAL_STATE_GROUP if term in text)
    if internal_hits > 0:
        score += 3
        reasons.append(f"internal_state_group matched ({internal_hits} terms)")
    token_hits = sum(1 for term in _TOKEN_GROUP if term in text)
    if token_hits > 0:
        score += 2
        reasons.append(f"token_group matched ({token_hits} terms)")
    detection_hits = sum(1 for term in _DETECTION_GROUP if term in text)
    if detection_hits > 0:
        score += 2
        reasons.append(f"detection_group matched ({detection_hits} terms)")
    must_hits = 0
    for term in must_include:
        if term.lower() in text:
            must_hits += 1
    if must_hits > 0:
        bonus = min(must_hits, 3)
        score += bonus
        reasons.append(f"must_include matched ({must_hits}/{len(must_include)})")
    negative_hits = sum(1 for term in _NEGATIVE_GROUP if term in text)
    if negative_hits > 0:
        penalty = negative_hits * 2
        score -= penalty
        reasons.append(f"negative_terms penalized (-{penalty})")
        flags.append(f"negative_match_{negative_hits}")
    title_lower = title.lower()
    strong_neg_hits = [term for term in _STRONG_DOMAIN_NEGATIVES if term in title_lower]
    has_strong_negative = len(strong_neg_hits) > 0
    if has_strong_negative:
        flags.append(f"strong_domain_negative: {', '.join(strong_neg_hits)}")
        title_internal_hits = sum(1 for term in _INTERNAL_STATE_GROUP if term in title_lower)
        if title_internal_hits == 0:
            reasons.append(f"strong domain negative in title without internal state terms: capped at medium")
    has_core = hallucination_hits > 0 or internal_hits > 0
    has_support = llm_hits > 0 or detection_hits > 0
    if score >= 7 and has_core and has_support:
        label = "high"
    elif score >= 4:
        label = "medium"
    else:
        label = "low"
    if has_strong_negative:
        title_internal_hits = sum(1 for term in _INTERNAL_STATE_GROUP if term in title_lower)
        if title_internal_hits == 0 and label == "high":
            label = "medium"
            reasons.append("domain negative cap applied: high -> medium")
    return {
        "relevance_score": score,
        "relevance_label": label,
        "relevance_reasons": reasons,
        "relevance_flags": flags,
        "strong_negative_flag": has_strong_negative,
    }


def _compute_ranking_score(relevance: dict, metadata_score: int, year_int: int) -> tuple[int, int, int]:
    """Combine relevance + metadata + recency into a single ranking tuple (higher = better)."""
    label_bonus = {"high": 100, "medium": 50, "low": 0}
    rel_score = relevance["relevance_score"] + label_bonus.get(relevance["relevance_label"], 0)
    return (rel_score, metadata_score, year_int)


def _score_candidate(rec: dict) -> tuple[int, int, int, str]:
    """Score a canonical candidate. Returns (ranking_score, rel_score, year_int, title_lower)."""
    meta_score = 0
    stable_ids = rec.get("stable_ids", {})
    has_stable = any(stable_ids.get(k) for k in ("doi", "arxiv_id", "semantic_scholar_id", "openalex_id"))
    if has_stable:
        meta_score += 2
    else:
        meta_score -= 1
    if rec.get("abstract", "").strip():
        meta_score += 2
    else:
        meta_score -= 2
    if rec.get("retrieved_at"):
        meta_score += 1
    source = rec.get("source", "")
    if source in ("arxiv", "openreview", "openalex"):
        meta_score += 1
    if rec.get("authors"):
        meta_score += 1
    if rec.get("venue"):
        meta_score += 1
    if source == "manual" and not rec.get("url", "").strip():
        meta_score -= 1
    try:
        year_int = int(str(rec.get("year", "")).strip())
    except (ValueError, TypeError):
        year_int = 0
    relevance_label = rec.get("relevance_label", "low")
    relevance_score = rec.get("relevance_score", 0)
    ranking_score_tuple = _compute_ranking_score(
        {"relevance_score": relevance_score, "relevance_label": relevance_label},
        meta_score,
        year_int,
    )
    title_lower = rec.get("title", "").lower().strip()
    return (ranking_score_tuple[0], relevance_score, year_int, title_lower)
