from __future__ import annotations

import re
from bs4 import BeautifulSoup, Tag

from legal_data.models import ProcessArticle

ARTICLE_ID_RE = re.compile(r"^Artículo\s+([\dA-Za-z.-]+)")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_heading(heading: str) -> tuple[str, str]:
    heading = normalize_text(heading)
    match = ARTICLE_ID_RE.match(heading)
    if not match:
        return heading, heading
    article_id = match.group(1).replace('.-', '').replace('.', '')
    return article_id, heading


def parse_cpp_html(html: str, source_url: str) -> list[ProcessArticle]:
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("div.td-post-content")
    if content is None:
        raise RuntimeError("No se encontró contenedor principal td-post-content")

    articles: list[ProcessArticle] = []
    current_heading: str | None = None
    current_id: str | None = None
    current_paragraphs: list[str] = []
    current_jurisprudence_url: str | None = None

    def flush_current_article() -> None:
        nonlocal current_heading, current_id, current_paragraphs, current_jurisprudence_url
        if current_heading and current_id:
            articles.append(
                ProcessArticle(
                    article_id=current_id,
                    heading=current_heading,
                    title=current_heading,
                    text="\n".join(current_paragraphs).strip(),
                    jurisprudence_url=current_jurisprudence_url,
                    source_url=source_url,
                    keyword_hits={"strong": [], "medium": [], "context": [], "negative": []},
                    heuristic_score=0,
                    candidate_status="unscored",
                )
            )
        current_heading = None
        current_id = None
        current_paragraphs = []
        current_jurisprudence_url = None

    for child in content.children:
        if not isinstance(child, Tag):
            continue

        if child.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            heading_text = normalize_text(child.get_text(" ", strip=True))
            flush_current_article()
            if child.name == "h4" and heading_text.startswith("Artículo "):
                current_id, current_heading = split_heading(heading_text)
            continue

        if current_heading is None:
            continue

        if child.name == "p":
            p_text = normalize_text(child.get_text(" ", strip=True))
            if not p_text:
                continue
            if p_text.lower().startswith("ver jurisprudencia"):
                a = child.find("a")
                current_jurisprudence_url = a.get("href") if a else None
            else:
                current_paragraphs.append(p_text)

    flush_current_article()

    return articles
