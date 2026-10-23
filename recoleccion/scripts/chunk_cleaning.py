"""Limpieza determinista de chunks: quita texto que no aporta nada a la recuperación ni a la generación.

Reglas (cada una cuenta cuántos chunks y caracteres toca; ver el informe que escribe consolidate_document_chunks.py):

  enlaces_acortados     "(link: bit.ly/...)" y similares, en cualquier tipo.
  notas_historial       líneas "* Artículo modificado/incorporado/reubicado por la Ley N, publicada el ..." del CP/CPP/Ley:
                        historial legislativo, no contenido normativo vigente. Se conservan las notas de DEROGACIÓN o
                        inconstitucionalidad ("** Inciso derogado tácitamente..."), porque cambian el sentido del texto.
  encabezados_finales   líneas en MAYÚSCULAS al final de un artículo (encabezado del capítulo/título que sigue).
  marcador_nuevo        "Título: NUEVO: ..." -> "Título: ..." (resto de la reescritura de jurisprudencia).
  boilerplate_web       cabecera/menús/botones/pie de las páginas gob.pe (tipo_05): se conserva solo el cuerpo.
  titulos_limpiados     en el campo `title`: marcador NUEVO:, asterisco de nota al pie y espacios antes de la puntuación.
  pagina_de_navegacion  (eliminación del chunk) páginas de tipo_05 que solo son menú y listado de publicaciones.
  sin_contenido_tras_limpieza  (eliminación del chunk) chunks cuyo único texto era una nota (p. ej. artículo reubicado).

La limpieza es idempotente: limpiar un texto ya limpio no lo cambia.
"""
from __future__ import annotations

import re
from collections import Counter

LINK_RE = re.compile(r"[ \t]*\((?:link|enlace)\s*:[^)]*\)", re.IGNORECASE)
NOTE_RE = re.compile(r"^\s*\*+\s*(?:[\wáéíóúñ]+\s+){0,3}?(?:modif\s*icad|incorporad|reubicad|sustituid|adicionad|renumerad)", re.IGNORECASE)
HEADING_RE = re.compile(r"^(LIBRO|SECCI[ÓO]N|T[ÍI]TULO|CAP[ÍI]TULO|SUBCAP[ÍI]TULO)\b", re.IGNORECASE)

WEB_MARK = " - Plataforma del Estado Peruano Saltar a contenido principal Texto de búsqueda en gob.pe Inicio El Estado "
WEB_TAIL_RE = re.compile(r"\s(?:Último cambio\b|Enlaces relacionados\b|Imprimir Compartir\b|Sobre el Estado Peruano\b)")
ATTACH_RE = re.compile(r"(?<![\wáéíóúñÁÉÍÓÚÑ])(?:[A-ZÁÉÍÓÚÑ0-9.\-/°]+\s+){1,16}PDF\s+[\d.,]+\s*[KM]B\s+Descargar\s*")
MIN_CONTENT_CHARS = 40
BUTTONS_RE = re.compile(r"\s*\b(?:Ir al servicio|Descargar|Leer más)\b\s*")


def _is_heading_line(line: str) -> bool:
    s = line.strip()
    letters = [c for c in s if c.isalpha()]
    if not s or len(letters) < 6 or not all(c.isupper() for c in letters):
        return False
    if re.match(r"^ART[ÍI]CULO\b", s):
        return False
    return len(s.split()) >= 2 or bool(HEADING_RE.match(s))


def clean_text(text: str, source_type: str, stats: Counter) -> str:
    original = text
    t = text.replace("\r\n", "\n").replace("\r", "\n")

    def count(rule: str, before: str, after: str) -> None:
        if before != after:
            stats[f"{rule}:chunks"] += 1
            stats[f"{rule}:caracteres"] += len(before) - len(after)

    # 1. enlaces acortados
    new = LINK_RE.sub("", t)
    count("enlaces_acortados", t, new)
    t = new

    if source_type in ("tipo_01_ley_30364", "tipo_02_codigo_penal", "tipo_03_codigo_procesal_penal"):
        # 2. notas de historial legislativo (una línea cada una)
        lines = t.split("\n")
        kept = [ln for ln in lines if not NOTE_RE.match(ln)]
        new = "\n".join(kept)
        count("notas_historial", t, new)
        t = new
        # 3. encabezados de capítulo/título pegados al final
        lines = t.split("\n")
        while lines and (not lines[-1].strip() or _is_heading_line(lines[-1])):
            lines.pop()
        new = "\n".join(lines)
        count("encabezados_finales", t, new)
        t = new

    if source_type == "tipo_04_jurisprudencia":
        new = re.sub(r"(?m)^(T[ií]tulo:\s*)NUEVO:\s*", r"\1", t)
        count("marcador_nuevo", t, new)
        t = new

    if source_type == "tipo_05_documentos_institucionales":
        new = _clean_web_page(t)
        count("boilerplate_web", t, new)
        t = new

    # espacios sobrantes (sin tocar el contenido)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def _clean_web_page(t: str) -> str:
    """Páginas gob.pe aplanadas en una línea: 'Título - Tipo - Entidad - Plataforma ... Inicio El Estado <ENT> <ruta> Título Título cuerpo ...'."""
    if WEB_MARK in t:
        title = t.split(" - ", 1)[0].strip()
        rest = t.split(WEB_MARK, 1)[1]
        first = rest.find(title)
        second = rest.find(title, first + len(title)) if first >= 0 else -1
        if second >= 0:
            rest = rest[second + len(title):]
        elif first >= 0:
            rest = rest[first + len(title):]
        t = rest.strip()
    m = WEB_TAIL_RE.search(t)
    if m:
        t = t[: m.start()]
    t = ATTACH_RE.sub(" ", t)
    t = BUTTONS_RE.sub(" ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def clean_title(title: str, stats: Counter) -> str:
    """Quita del título el marcador NUEVO:, los asteriscos de nota al pie y los espacios antes de la puntuación."""
    t = title or ""
    new = re.sub(r"^\s*NUEVO:\s*", "", t)
    new = re.sub(r"\s*\*+\s*$", "", new)
    new = re.sub(r"\s+([.,;:])", r"\1", new)
    new = re.sub(r"\s{2,}", " ", new).strip()
    if new != t:
        stats["titulos_limpiados:chunks"] += 1
    return new


def is_navigation_page(chunk: dict, text: str) -> bool:
    return chunk.get("source_type") == "tipo_05_documentos_institucionales" and (
        text.count("Leer más") >= 3 or "Todas las categorías" in text or "Menú Inicio" in text
    )


def clean_chunks(chunks: list[dict]) -> tuple[list[dict], dict]:
    stats: Counter = Counter()
    out, dropped = [], []
    for c in chunks:
        if is_navigation_page(c, c["text"]):          # se decide sobre el texto original (con el menú)
            dropped.append({"chunk_id": c["chunk_id"], "reason": "pagina_de_navegacion", "chars": len(c["text"])})
            continue
        new_text = clean_text(c["text"], c.get("source_type", ""), stats)
        if len(new_text.strip()) < MIN_CONTENT_CHARS:      # p. ej. artículos "reubicados" cuyo único texto era la nota
            dropped.append({"chunk_id": c["chunk_id"], "reason": "sin_contenido_tras_limpieza", "chars": len(c["text"])})
            continue
        nc = dict(c)
        nc["text"] = new_text
        if "title" in nc:
            nc["title"] = clean_title(nc["title"], stats)
        out.append(nc)
    report = {
        "chunks_entrada": len(chunks), "chunks_salida": len(out), "chunks_eliminados": dropped,
        "caracteres_antes": sum(len(c["text"]) for c in chunks), "caracteres_despues": sum(len(c["text"]) for c in out),
        "por_regla": {k: v for k, v in sorted(stats.items())},
    }
    return out, report
