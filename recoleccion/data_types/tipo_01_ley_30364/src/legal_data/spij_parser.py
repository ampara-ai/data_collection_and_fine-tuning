from __future__ import annotations

import re
from dataclasses import dataclass
from bs4 import BeautifulSoup

from legal_data.law_model import Article, LawDocument


ARTICLE_RE = re.compile(
    r'^\s*["“”]?\s*art[ií]culo\s+(\d+[A-Za-z]?(?:-[A-Za-z])?)\.?\s*(.*)$',
    re.IGNORECASE,
)

MODIFICATION_NOTE_RE = re.compile(
    r"^\(?\*+\)?\s*"
    r"(art[ií]culo|p[aá]rrafo|literal|extremo|disposici[oó]n)"
    r"\s+(modificado|incorporado|sustituido|derogado)",
    re.IGNORECASE,
)

REPLACEMENT_INTRO_RE = re.compile(
    r"cuyo texto es el siguiente",
    re.IGNORECASE,
)

EDITORIAL_RE = re.compile(
    r"^\(?\*+\)?\s*|"
    r"^CONCORDANCIAS:|"
    r"^OTRAS CONCORDANCIAS|"
    r"^VER TEXTO ÚNICO ORDENADO|"
    r"^De conformidad con",
    re.IGNORECASE,
)

STRUCTURAL_RE = re.compile(
    r"^(T[IÍ]TULO|CAP[IÍ]TULO|SUBCAP[IÍ]TULO)\b",
    re.IGNORECASE,
)


# Fin del articulado: el último artículo de cada tramo absorbía todo lo que venía después (disposiciones
# complementarias, firmas y el listado de normas conexas) porque nada cerraba el artículo en curso.
SECTION_RE = re.compile(
    r"^DISPOSICIONES?\s+COMPLEMENTARIAS?\s+(FINALES?|TRANSITORIAS?|MODIFICATORIAS?|DEROGATORIAS?)\s*$",
    re.IGNORECASE,
)
SIGNATURE_RE = re.compile(r"^Comun[ií]quese\b", re.IGNORECASE)
PROVISION_RE = re.compile(
    r"^(PRIMERA|SEGUNDA|TERCERA|CUARTA|QUINTA|SEXTA|S[EÉ]PTIMA|OCTAVA|NOVENA|D[EÉ]CIMA|[UÚ]NICA)\.\s*(.*)$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = re.sub(r"\s+", " ", text).strip()

    # El SPIJ suele envolver textos modificados en comillas.
    text = re.sub(r'^["\']\s*', "", text)
    text = re.sub(r'\s*["\']$', "", text)

    return text.strip()


def html_to_text_blocks(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "lxml")

    # Eliminar scripts/styles si existieran.
    for tag in soup(["script", "style"]):
        tag.decompose()

    blocks: list[str] = []

    for node in soup.find_all(["p", "h1", "h2", "h3", "li"]):
        text = node.get_text(" ", strip=True)
        text = normalize_text(text)
        if text:
            blocks.append(text)

    return blocks


def is_article_heading(block: str) -> re.Match | None:
    return ARTICLE_RE.match(normalize_text(block))


def is_editorial_note(block: str) -> bool:
    block = normalize_text(block)

    if EDITORIAL_RE.search(block):
        return True

    if MODIFICATION_NOTE_RE.search(block):
        return True

    if REPLACEMENT_INTRO_RE.search(block) and MODIFICATION_NOTE_RE.search(block):
        return True

    return False


def strip_obsolete_marker(text: str) -> str:
    """
    Quita marcadores editoriales tipo (*), (**), pero no borra el contenido normativo.
    """
    text = normalize_text(text)
    text = re.sub(r"\s*\(\*+\)\s*$", "", text)
    text = re.sub(r"\s*\(\*+\)\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def line_has_obsolete_marker(text: str) -> bool:
    return bool(re.search(r"\(\*+\)\s*$", normalize_text(text)))

MODIFIED_NOTE_RE = re.compile(
    r"^\(?\*+\)?\s*"
    r"(art[ií]culo|p[aá]rrafo|literal|extremo|numeral|disposici[oó]n)"
    r"\s+modificado\b",
    re.IGNORECASE,
)

INCORPORATED_NOTE_RE = re.compile(
    r"^\(?\*+\)?\s*"
    r"(art[ií]culo|p[aá]rrafo|literal|extremo|numeral|disposici[oó]n)"
    r"\s+incorporado\b",
    re.IGNORECASE,
)
def clean_article_lines(lines: list[str]) -> list[str]:
    """
    Limpieza intra-artículo:
    - elimina notas editoriales;
    - elimina texto antiguo solo cuando la nota posterior dice 'modificado';
    - conserva texto vigente cuando la nota posterior dice 'incorporado'.
    """
    cleaned: list[str] = []
    pending_marked_idx: int | None = None

    for raw in lines:
        line = normalize_text(raw)

        if not line:
            continue

        if line.upper().startswith("CONCORDANCIAS"):
            continue

        is_modified_note = bool(MODIFIED_NOTE_RE.search(line))
        is_incorporated_note = bool(INCORPORATED_NOTE_RE.search(line))
        is_any_editorial = is_editorial_note(line)

        if is_any_editorial:
            # Solo borrar la línea anterior si la nota dice MODIFICADO.
            # Si dice INCORPORADO, la línea anterior es justamente el texto nuevo.
            if is_modified_note and pending_marked_idx is not None:
                if 0 <= pending_marked_idx < len(cleaned):
                    cleaned.pop(pending_marked_idx)

            pending_marked_idx = None
            continue

        marked = line_has_obsolete_marker(line)
        line = strip_obsolete_marker(line)

        if not line:
            continue

        cleaned.append(line)

        if marked:
            pending_marked_idx = len(cleaned) - 1
        else:
            pending_marked_idx = None

    return cleaned


def article_sort_key(article_id: str) -> tuple[int, str]:
    """
    Ordena 1, 2, 8, 15-B, 16-D, etc.
    """
    m = re.match(r"^(\d+)(.*)$", article_id)
    if not m:
        return (10**9, article_id)
    return (int(m.group(1)), m.group(2) or "")


def parse_spij_detail_to_law(detail: dict) -> LawDocument:
    html = detail.get("textoCompleto") or ""
    blocks = html_to_text_blocks(html)

    articles_by_id: dict[str, Article] = {}

    current_article_id: str | None = None
    current_heading: str | None = None
    current_lines: list[str] = []

    # Texto que queda fuera de los artículos: disposiciones complementarias y anexo posterior a la firma.
    provisions: list[dict] = []
    annex_lines: list[str] = []
    section: str | None = None
    in_annex = False

    def flush_current_article() -> None:
        nonlocal current_article_id, current_heading, current_lines

        if current_article_id is None:
            return

        cleaned_lines = clean_article_lines(current_lines)

        if not cleaned_lines:
            return

        # Recalcular heading desde la primera línea limpia si es artículo.
        first = cleaned_lines[0]
        m = is_article_heading(first)

        heading = first if m else current_heading
        text = "\n".join(cleaned_lines).strip()

        # Regla central:
        # si un mismo artículo aparece de nuevo más adelante,
        # asumimos que la versión posterior del SPIJ es la más vigente.
        articles_by_id[current_article_id] = Article(
            article_id=current_article_id,
            heading=heading,
            text=text,
        )

    for block in blocks:
        block = normalize_text(block)

        # Saltar encabezados estructurales. Si quieres conservarlos, podrías guardarlos como metadata.
        if STRUCTURAL_RE.match(block):
            continue

        if SECTION_RE.match(block) or SIGNATURE_RE.match(block):
            # Cierra el artículo en curso: lo que sigue no es parte de él.
            flush_current_article()
            current_article_id, current_heading, current_lines = None, None, []
            if SIGNATURE_RE.match(block):
                in_annex = True
                annex_lines.append(block)
            else:
                section = SECTION_RE.match(block).group(1).upper()
            continue

        if in_annex:
            annex_lines.append(block)
            continue

        match = is_article_heading(block)

        if match:
            found_article_id = match.group(1)

            # Si aparece un artículo distinto, cerramos el anterior.
            if current_article_id is not None and found_article_id != current_article_id:
                flush_current_article()
                current_lines = []

            # Si aparece el mismo artículo de nuevo, es probablemente versión modificada.
            # Cerramos/sobrescribimos la anterior y empezamos nueva versión.
            elif current_article_id is not None and found_article_id == current_article_id:
                flush_current_article()
                current_lines = []

            current_article_id = found_article_id
            current_heading = block
            current_lines = [block]
            continue

        if current_article_id is not None:
            current_lines.append(block)
        elif section is not None:
            m = PROVISION_RE.match(block)
            if m or not provisions or provisions[-1]["section"] != section:
                provisions.append({"section": section, "number": m.group(1).upper() if m else None,
                                   "title": m.group(2).strip() if m else block, "lines": [block]})
            else:
                provisions[-1]["lines"].append(block)

    flush_current_article()

    complementary_provisions = [
        {"section": p["section"], "number": p["number"], "title": p["title"], "text": "\n".join(p["lines"])}
        for p in provisions
    ]
    annexes = [{"unit_type": "post_signature_text", "text": "\n".join(annex_lines)}] if annex_lines else []

    articles = [
        articles_by_id[k]
        for k in sorted(articles_by_id.keys(), key=article_sort_key)
    ]

    return LawDocument(
        norm_id=detail.get("id", "H1141065"),
        code=detail.get("codigoNorma", "LEY 30364"),
        title=BeautifulSoup(detail.get("sumilla", ""), "lxml").get_text(" ", strip=True),
        source="SPIJ",
        articles=articles,
        complementary_provisions=complementary_provisions,
        annexes=annexes,
        metadata={
            "fechaPublicacion": detail.get("fechaPublicacion"),
            "sector": detail.get("sector"),
            "dispositivoLegal": detail.get("dispositivoLegal"),
            "parser_strategy": "spij_latest_article_version_with_partial_mod_cleanup_and_section_boundaries",
        },
    )