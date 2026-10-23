from __future__ import annotations

from legal_data.config import STRONG_KEYWORDS, MEDIUM_KEYWORDS, CONTEXT_KEYWORDS, NEGATIVE_HINTS
from legal_data.models import PenalArticle


def _hits(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [kw for kw in keywords if kw in lowered]


def score_article(article: PenalArticle) -> PenalArticle:
    title = article.title.lower()
    text = article.text.lower()
    jurisprudence_text = (article.jurisprudence_url or "").lower()

    strong_title = _hits(title, STRONG_KEYWORDS)
    strong_text = _hits(text, STRONG_KEYWORDS)
    medium_title = _hits(title, MEDIUM_KEYWORDS)
    medium_text = _hits(text, MEDIUM_KEYWORDS)
    context_title = _hits(title, CONTEXT_KEYWORDS)
    context_text = _hits(text, CONTEXT_KEYWORDS)
    negative_title = _hits(title, NEGATIVE_HINTS)
    negative_text = _hits(text, NEGATIVE_HINTS)

    score = 0
    score += 8 * len(strong_title)
    score += 6 * len(strong_text)
    score += 4 * len(medium_title)
    score += 2 * len(medium_text)
    score += 2 * len(context_title)
    score += 1 * len(context_text)

    # bonuses por coocurrencia útil
    if strong_text and (medium_text or medium_title or context_text):
        score += 4

    if (
        ("mujer" in medium_text or "mujeres" in medium_text or "mujer" in medium_title)
        and ("lesiones" in medium_text or "amenaza" in medium_text or "amenazas" in medium_text or "violencia familiar" in strong_text)
    ):
        score += 5

    if "grupo familiar" in strong_text or "integrantes del grupo familiar" in strong_text:
        score += 6

    if article.jurisprudence_url and any(term in jurisprudence_text for term in ["violencia", "feminicidio", "mujer", "familiar"]):
        score += 2

    # penalizaciones de ruido obvio
    score -= 4 * len(negative_title)
    score -= 2 * len(negative_text)

    # artículos demasiado generales: solo sobreviven si tienen señales fuertes
    is_general_article = article.article_id in {"36", "46", "57"}
    if is_general_article and not strong_title and not strong_text:
        score -= 6

    if score >= 14:
        status = "candidate_strong"
    elif score >= 8:
        status = "candidate_medium"
    elif score >= 5:
        status = "candidate_weak"
    else:
        status = "discarded"

    article.keyword_hits = {
        "strong": sorted(set(strong_title + strong_text)),
        "medium": sorted(set(medium_title + medium_text)),
        "context": sorted(set(context_title + context_text)),
        "negative": sorted(set(negative_title + negative_text)),
    }
    article.heuristic_score = score
    article.candidate_status = status
    return article


def summarize_scored_articles(articles: list[PenalArticle]) -> dict:
    summary = {
        "total_articles": len(articles),
        "candidate_strong": 0,
        "candidate_medium": 0,
        "candidate_weak": 0,
        "discarded": 0,
    }
    for article in articles:
        summary[article.candidate_status] += 1
    return summary
