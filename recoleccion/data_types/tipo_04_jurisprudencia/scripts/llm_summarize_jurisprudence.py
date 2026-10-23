#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import concurrent.futures
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_json  # Restauramos el import para guardar

INPUT_JSON = PROCESSED_DIR / "jurisprudence_entry_content.json"
OUTPUT_JSON = PROCESSED_DIR / "jurisprudence_context_units.json"

# --- MODELOS MEJORADOS ---

class ApplicableNorm(BaseModel):
    norm_standardized: Literal[
        "Codigo Penal",
        "Codigo Procesal Penal (NCPP/CPP de 2004)",
        "Codigo de Procedimientos Penales (CdePP de 1940)",
        "Codigo Civil",
        "Codigo Procesal Civil",
        "Constitucion Politica del Peru",
        "Ley Organica del Poder Judicial (LOPJ)",
        "Codigo de los Ninos y Adolescentes",
        "Ley 30364 (Violencia contra la mujer)",
        "Otro"
    ] = Field(description="DEBES clasificar la norma en una de estas categorías exactas.")
    norm_raw_text: str = Field(description="El nombre exacto o siglas de la norma tal como aparece en el texto (ej. 'NCPP').")
    articles: list[str] = Field(default_factory=list, description="Lista de artículos específicos, ej. ['8', '100', '447.3']")


class AntecedentSignals(BaseModel):
    document_type_category: Literal[
        "expediente_superior_juzgado", 
        "casacion_depende", 
        "casacion_doctrina_vinculante", 
        "acuerdo_plenario", 
        "recurso_nulidad",
        "otro"
    ] = Field(description="Categoría del documento según la tabla de reglas.")
    has_factual_background: bool = Field(description="¿Contiene un resumen de los hechos reales del caso?")
    pdf_utility_score: Literal["alta", "media", "baja", "nula"] = Field(description="Alta si tiene hechos ricos; Nula si es doctrina pura.")
    antecedent_reason: str = Field(description="Breve justificación de la clasificación.")


class JurisprudenceSummaryModel(BaseModel):
    title: str | None = None
    document_kind_standardized: Literal[
        "Casacion",
        "Acuerdo Plenario",
        "Recurso de Nulidad",
        "Expediente / Sentencia de Instancia",
        "Habeas Corpus / Amparo (TC)",
        "Resolucion Administrativa",
        "Otro"
    ] = Field(description="Clasificación estandarizada del tipo de resolución.")
    document_kind_raw: str | None = Field(description="Tipo de documento extraído textualmente (Ej. 'Acuerdo Plenario Extraordinario').")
    facts_summary: str | None = Field(description="Resumen de los hechos. Null o vacío si es doctrina pura.")
    legal_issue: str | None = Field(description="El problema jurídico central a resolver.")
    holding: str | None = Field(description="La regla de derecho o decisión principal (Ratio Decidendi).")
    reasoning_summary: str | None = None
    outcome: str | None = None
    applicable_norms: list[ApplicableNorm] = Field(default_factory=list)
    violence_family_relevance: str | None = None
    procedural_relevance: str | None = None
    practical_context_summary: str | None = None
    keywords: list[str] = Field(default_factory=list)
    llm_relevance_score: float | None = None
    needs_review: bool = False
    detected_resolution_label: str | None = None
    detected_case_number: str | None = None
    pdf_url_mapped: str | None = Field(description="URL exacta del PDF, extraída usualmente de la etiqueta [pdf].")
    antecedent_signals: AntecedentSignals


# --- PROMPT MEJORADO ---

SYSTEM_PROMPT = """Eres un analista jurídico experto en derecho penal y procesal peruano. Tu objetivo es procesar jurisprudencia (formateada en Markdown extraído de HTML) para estructurar su contenido y alimentar un sistema de búsqueda (RAG).

TAREAS PRINCIPALES:
1. Sintetizar los hechos, el problema jurídico y la decisión. Si el documento es doctrina pura sin un caso base, deja el campo de hechos nulo.
2. Identificar las normas y artículos aplicados. DEBES estandarizar el nombre de la norma y el tipo de documento usando estrictamente las opciones permitidas en el schema (ej. si el texto dice "NCPP", clasifícalo como "Codigo Procesal Penal (NCPP/CPP de 2004)" y guarda "NCPP" en raw).
3. Localizar OBLIGATORIAMENTE la URL del documento original si existe (usualmente precedida por la etiqueta "[pdf]").
4. Evaluar la riqueza de los "antecedentes/hechos" para determinar si vale la pena descargar el PDF completo.

REGLAS ESTRICTAS DE CLASIFICACIÓN DE ANTECEDENTES (Para antecedent_signals):
- Expedientes (Salas Superiores, Juzgado Mixto/Familia, Juzgado Penal): SÍ tienen hechos. (Utilidad PDF: alta).
- Casación (Corte Suprema regular): Depende del contenido. (Utilidad PDF: media o alta).
- Casación con Doctrina Vinculante: NO tienen hechos, es doctrina. (Utilidad PDF: nula o baja).
- Acuerdo Plenario: NO tienen hechos, es doctrina pura. (Utilidad PDF: nula).
- Recurso de Nulidad (R.N.): Depende, a veces tienen hechos. (Utilidad PDF: media).

INSTRUCCIONES DE FORMATO:
- Responde ÚNICAMENTE con un JSON válido que cumpla con el schema solicitado.
- No inventes datos, números de expediente, URLs ni hechos que no estén explícitamente en el texto.
- Extrae la URL del PDF exactamente como aparece en el texto, sin modificarla."""


def summarize_entry(client: OpenAI, model: str, item: dict) -> dict:
    payload = {
        "entry_title_raw": item.get("entry_title_raw"),
        "document_kind_hint": item.get("document_kind"),
        "index_page_title": item.get("index_page_title"),
        "entry_url": item.get("entry_url"),
        "pdf_url_hint": item.get("pdf_url"),
        "combined_text": item.get("combined_text"),
        "provenance_sources": item.get("provenance_sources") or [],
    }
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Devuelve SOLO JSON válido ajustado al schema conceptual definido. "
                    "Asegúrate de aplicar correctamente las reglas de clasificación de antecedentes y mapear la URL del PDF.\n\n"
                    f"PAYLOAD:\n{json.dumps(payload, ensure_ascii=False)}"
                    f"el schema que deberias devolver es este : {JurisprudenceSummaryModel.model_json_schema()}"
                ),
            },
        ],
        stream=False,
        response_format={"type": "json_object"},
        extra_headers={
            "HTTP-Referer": "https://openclaw.local",
            "X-Title": os.environ.get("APP_NAME", "peru-legal-rag-data"),
        },
    )
    
    content = response.choices[0].message.content if response.choices and response.choices[0].message else None
    if not content:
        raise RuntimeError("empty model response")
        
    parsed = JurisprudenceSummaryModel.model_validate(json.loads(content))
    
    return {
        "entry_id": item.get("entry_id"),
        "index_page_id": item.get("index_page_id"),
        "entry_url": item.get("entry_url"),
        "pdf_url": item.get("pdf_url"),
        "provenance_sources": item.get("provenance_sources") or [],
        "context_unit": parsed.model_dump(mode="json"),
    }


def process_single_item(client: OpenAI, model: str, item: dict) -> dict:
    """Función worker con logs incorporados para seguimiento concurrente."""
    entry_id = item.get("entry_id", "ID_DESCONOCIDO")
    
    # Log de inicio
    print(f"Iniciando procesamiento de: {entry_id} ...")
    
    if item.get("content_status") != "success" or not item.get("combined_text"):
        # Log de salto (skipped)
        print(f"[SKIPPED] {entry_id} procesado | status: skipped (sin texto válido)")
        return {
            "entry_id": entry_id, 
            "index_page_id": item.get("index_page_id"), 
            "entry_url": item.get("entry_url"), 
            "pdf_url": item.get("pdf_url"), 
            "provenance_sources": item.get("provenance_sources") or [], 
            "context_unit": None, 
            "status": "skipped"
        }
        
    try:
        result = summarize_entry(client, model, item)
        # Log de éxito
        print(f"[SUCCESS] {entry_id} procesado | status: success")
        return {**result, "status": "success"}
    except Exception as exc:
        # Log de error
        print(f"[ERROR] {entry_id} procesado | status: error | detalle: {exc}")
        return {
            "entry_id": entry_id, 
            "index_page_id": item.get("index_page_id"), 
            "entry_url": item.get("entry_url"), 
            "pdf_url": item.get("pdf_url"), 
            "provenance_sources": item.get("provenance_sources") or [], 
            "context_unit": None, 
            "status": f"error: {exc}"
        }


def main() -> None:
    load_dotenv()
    client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    model = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    
    try:
        items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo de entrada en {INPUT_JSON}")
        return

    outputs = []
    
    print(f"Arrancando el motor. Procesando un total de {len(items)} documentos con 2 workers concurrentes...\n")
    print("-" * 50)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Nota: Aquí quitamos el [:3] para procesar TODO el archivo.
        futures = {executor.submit(process_single_item, client, model, item): item for item in items}
        
        for future in concurrent.futures.as_completed(futures):
            item_ref = futures[future]
            try:
                result = future.result()
                outputs.append(result)
                # Los logs individuales ahora los maneja process_single_item
            except Exception as exc:
                print(f"Fallo a nivel de hilo para entry_id {item_ref.get('entry_id')}: {exc}")

    print("-" * 50)
    print("💾 Guardando resultados en disco...")
    write_json(OUTPUT_JSON, outputs)
    
    print("\n--- RESUMEN FINAL ---")
    print(json.dumps({
        "entries_total": len(outputs),
        "summarized_success": sum(1 for x in outputs if x.get('status') == 'success'),
        "has_factual_background_yes": sum(1 for x in outputs if (x.get('context_unit') or {}).get('antecedent_signals', {}).get('has_factual_background') is True),
        "pdf_utility_high_or_medium": sum(1 for x in outputs if (x.get('context_unit') or {}).get('antecedent_signals', {}).get('pdf_utility_score') in ["alta", "media"]),
        "output_path": str(OUTPUT_JSON),
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()