BOOTSTRAP_PARSE_PROMPT = """
Eres un analista jurídico. Recibirás contenido de una norma peruana y debes devolver una representación estructurada de la ley vigente.

Objetivo:
- ignorar notas históricas, trazabilidad redundante y anotaciones editoriales que no formen parte del texto vigente consolidado
- conservar literalmente el texto vigente de los artículos
- no resumir
- no inventar

Devuelve JSON con este esquema:
{
  "title": "...",
  "articles": [
    {"article_id": "1", "heading": "Artículo 1.- ...", "text": "texto literal vigente"}
  ],
  "complementary_provisions": [],
  "annexes": [],
  "notes": []
}
""".strip()

PDF_CLASSIFY_AND_EXTRACT_PROMPT = """
Eres un analista jurídico peruano. Recibirás imágenes de páginas de una publicación de El Peruano.

Tareas:
1. Determina si la publicación modifica directamente la Ley N° 30364.
2. Si no la modifica directamente pero establece un cambio regulatorio relacionado, repórtalo aparte.
3. Si modifica directamente la ley, devuelve operaciones estructuradas de cambio.
4. Si solo menciona la Ley 30364 de forma incidental, dilo claramente.

Devuelve JSON con este esquema:
{
  "affects_law_30364": true,
  "is_related_update": false,
  "summary": "...",
  "change_ops": [
    {
      "type": "replace_article",
      "article_id": "...",
      "heading": "...",
      "text": "..."
    }
  ],
  "related_update": null,
  "confidence": 0.0,
  "reasoning_brief": "..."
}
""".strip()
