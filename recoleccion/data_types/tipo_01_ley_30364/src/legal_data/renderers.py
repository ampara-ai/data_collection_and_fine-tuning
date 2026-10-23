from __future__ import annotations

from legal_data.law_model import LawDocument


def render_law_markdown(law: LawDocument) -> str:
    lines = [f"# {law.code}", "", law.title, ""]
    for article in law.articles:
        lines.append(f"## Artículo {article.article_id}")
        lines.append("")
        lines.append(article.text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"
