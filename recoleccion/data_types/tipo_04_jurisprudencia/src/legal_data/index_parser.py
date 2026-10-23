from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

CATEGORY_NAMES = {
    "Corte Suprema",
    "Corte Superior",
    "Legislación",
    "Juzgados",
    "Derecho comparado",
    "Corte IDH",
    "Corte Interamericana de Derechos Humanos",
}


def split_compound_entry_text(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    text = re.sub(r"\bNUEVO:\s+NUEVO:\s+", "NUEVO: ", text)
    parts = re.split(r"(?=(?:NUEVO:\s+)?[^\[]{12,}?\[[^\]]+\]\s*\.\s*Link:)", text)
    cleaned = []
    for part in parts:
        part = normalize_text(part)
        if not part:
            continue
        if part in CATEGORY_NAMES or part == "NUEVO:" or len(part) < 12:
            continue
        cleaned.append(part)
    return cleaned or ([text] if text not in CATEGORY_NAMES and text != "NUEVO:" else [])

RESOLUTION_PATTERNS = [
    r"(Casación\s+[^\]]+)",
    r"(Apelación\s+[^\]]+)",
    r"(RN\s+[^\]]+)",
    r"(Exp\.\s+[^\]]+)",
    r"(AP\s+[^\]]+)",
    r"(Queja\s+[^\]]+)",
    r"(Consulta\s+[^\]]+)",
    r"(Revisión de Sentencia\s+[^\]]+)",
    r"(Rev\.\s*Sent\.?[^\]]+)",
    r"(RA\s+[^\]]+)",
    r"(Pleno\s+[^\]]+)",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_concordances(block_text: str) -> list[dict[str, Any]]:
    items = []
    for part in block_text.split(";"):
        part = normalize_text(part)
        if not part or ":" not in part:
            continue
        code, refs = part.split(":", 1)
        code = normalize_text(code).replace(":", "")
        refs = normalize_text(refs)
        article_tokens = re.findall(r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?", refs)
        items.append({"code": code, "articles": article_tokens})
    return items


def extract_resolution_reference(text: str) -> str | None:
    for pattern in RESOLUTION_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return normalize_text(m.group(1))
    return None


def parse_resolution_metadata(reference: str | None) -> dict[str, Any]:
    if not reference:
        return {
            "resolution_type": None,
            "resolution_number": None,
            "resolution_year": None,
            "resolution_jurisdiction": None,
        }
    ref = normalize_text(reference)
    typ = ref.split(" ", 1)[0]
    year_match = re.search(r"(19|20)\d{2}", ref)
    year = int(year_match.group(0)) if year_match else None
    number_match = re.search(r"([0-9][0-9A-Za-z./-]*)", ref)
    number = number_match.group(1) if number_match else None
    jurisdiction = None
    if "," in ref:
        jurisdiction = normalize_text(ref.split(",", 1)[1])
    return {
        "resolution_type": typ,
        "resolution_number": number,
        "resolution_year": year,
        "resolution_jurisdiction": jurisdiction,
    }


def detect_entry_type(category: str, text: str, reference: str | None) -> str:
    lower = text.lower()
    if category == "Legislación":
        return "legislacion"
    if "doctrina legal" in lower:
        return "doctrina_legal"
    if category in {"Corte Suprema", "Corte Superior", "Juzgados", "Corte IDH", "Corte Interamericana de Derechos Humanos"}:
        return "jurisprudencia"
    return "otro"


def parse_index_entries(parsed_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for page in parsed_pages:
        raw_path = Path(page["raw_html_path"])
        html = raw_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")
        content = soup.select_one("div.td-post-content")
        if not content:
            continue

        article_heading = None
        concordances = []
        entry_counter = 0

        for node in content.find_all(["h2", "p"]):
            text = normalize_text(node.get_text(" ", strip=True))
            if not text:
                continue
            if text.startswith("Artículo ") and article_heading is None:
                article_heading = text
            if ("art." in text.lower() or "arts." in text.lower()) and ":" in text and any(code in text for code in ["CP", "NCPP", "C:", "CC", "CADH", "DADDH"]):
                parsed = parse_concordances(text)
                if parsed:
                    concordances = parsed

        nodes = [tag for tag in content.find_all(["h3", "li"]) if normalize_text(tag.get_text(" ", strip=True))]
        current_category = None
        seen_entry_texts = set()
        for tag in nodes:
            text = normalize_text(tag.get_text(" ", strip=True))
            if text in CATEGORY_NAMES:
                current_category = text
                continue
            if tag.name != "li" or not current_category:
                continue
            if text in CATEGORY_NAMES:
                continue
            parts = split_compound_entry_text(text)
            links = [a["href"] for a in tag.find_all("a", href=True) if "lpderecho.pe" in a["href"]]
            for idx, part in enumerate(parts):
                if part in CATEGORY_NAMES:
                    continue
                flags = []
                if part.startswith("NUEVO") or part.startswith("NUEVO:"):
                    flags.append("NUEVO")
                    part = re.sub(r"^NUEVO:\s*", "", part).strip()
                if not part or part == "NUEVO:" or len(part) < 12:
                    continue
                entry_link = links[min(idx, len(links)-1)] if links else None
                dedupe_key = entry_link or part
                if dedupe_key in seen_entry_texts:
                    continue
                seen_entry_texts.add(dedupe_key)
                short_link = links[-1] if links else None
                entry_counter += 1
                reference = extract_resolution_reference(part)
                metadata = parse_resolution_metadata(reference)
                entry_type = detect_entry_type(current_category, part, reference)
                entry_id = f"{page['id']}_e{entry_counter:04d}"
                related_norms = []
                if page.get("linked_articles"):
                    anchor_article = page["linked_articles"][0]
                    related_norms.append(
                        {
                            "code": anchor_article.get("source_dataset", ""),
                            "article_id": anchor_article.get("article_id"),
                            "relation_type": "page_anchor",
                            "confidence": "high",
                        }
                    )
                for c in concordances:
                    for article in c.get("articles", []):
                        related_norms.append(
                            {
                                "code": c.get("code"),
                                "article_id": article,
                                "relation_type": "page_concordance",
                                "confidence": "high",
                            }
                        )
                results.append(
                    {
                        "entry_id": entry_id,
                        "page_id": page["id"],
                        "page_source_url": page["jurisprudence_url"],
                        "entry_category": current_category,
                        "entry_type": entry_type,
                        "entry_prefix_flags": flags,
                        "entry_text": part,
                        "entry_title_candidate": part.split("[")[0].replace("Link:", "").strip(),
                        "resolution_reference_raw": reference,
                        "lp_entry_url": entry_link,
                        "short_link_url": short_link,
                        "page_anchor_code": None,
                        "page_anchor_article_id": page.get("linked_articles", [{}])[0].get("article_id"),
                        "page_anchor_article_heading": page.get("linked_articles", [{}])[0].get("heading"),
                        "page_concordances": concordances,
                        "related_norms": related_norms,
                        "domain_relevance_candidate": None,
                        **metadata,
                    }
                )
    return results
