from __future__ import annotations

from typing import Any


def apply_change_ops(law_data: dict[str, Any], change_ops: list[dict[str, Any]]) -> dict[str, Any]:
    articles = {a["article_id"]: a for a in law_data.get("articles", [])}

    for op in change_ops:
        op_type = op.get("type")
        if op_type == "replace_article":
            article_id = op["article_id"]
            articles[article_id] = {
                "article_id": article_id,
                "heading": op.get("heading") or f"Artículo {article_id}",
                "text": op["text"],
            }
        elif op_type == "add_article":
            article_id = op["article_id"]
            articles[article_id] = {
                "article_id": article_id,
                "heading": op.get("heading") or f"Artículo {article_id}",
                "text": op["text"],
            }
        elif op_type == "repeal_article":
            article_id = op["article_id"]
            if article_id in articles:
                del articles[article_id]
        elif op_type == "global_reference_rename":
            old = op["from"]
            new = op["to"]
            for article in articles.values():
                article["text"] = article["text"].replace(old, new)
        else:
            # En esta versión preliminar, cambios no soportados se ignoran,
            # pero deberían registrarse en el change log para revisión.
            continue

    law_data["articles"] = sorted(
        articles.values(),
        key=lambda a: a["article_id"],
    )
    return law_data
