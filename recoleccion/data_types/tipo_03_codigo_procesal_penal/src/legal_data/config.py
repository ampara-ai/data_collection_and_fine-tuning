from __future__ import annotations

SOURCE_PAGES = (
    {
        "part_id": "parte_1",
        "url": "https://lpderecho.pe/nuevo-codigo-procesal-penal-peruano-actualizado/",
        "raw_filename": "codigo_procesal_penal_lpderecho_parte_1.html",
        "required_article_ids": ("I", "445"),
    },
    {
        "part_id": "parte_2",
        "url": "https://lpderecho.pe/nuevo-codigo-procesal-penal/",
        "raw_filename": "codigo_procesal_penal_lpderecho_parte_2.html",
        "required_article_ids": ("446", "566"),
    },
)

EXPECTED_FIRST_NUMERIC_ARTICLE = 1
EXPECTED_LAST_NUMERIC_ARTICLE = 566

STRONG_KEYWORDS = [
    "víctima",
    "victima",
    "agraviado",
    "agraviada",
    "protección",
    "proteccion",
    "medidas de protección",
    "medidas de coerción",
    "medidas de coercion",
    "ministerio público",
    "ministerio publico",
    "policía",
    "policia",
    "fiscal",
    "denuncia",
    "investigación preparatoria",
    "investigacion preparatoria",
]

MEDIUM_KEYWORDS = [
    "querella",
    "declaración",
    "declaracion",
    "prueba anticipada",
    "testigo",
    "imputado",
    "audiencia",
    "flagrancia",
    "medidas limitativas",
    "intervención policial",
    "intervencion policial",
    "diligencia",
    "reparación civil",
    "reparacion civil",
    "acción penal",
    "accion penal",
]

CONTEXT_KEYWORDS = [
    "niño",
    "niña",
    "adolescente",
    "mujer",
    "mujeres",
    "grupo familiar",
    "violencia",
    "familiar",
    "sexual",
    "urgencia",
    "vulnerable",
]

NEGATIVE_HINTS = [
    "casación",
    "casacion",
    "nulidad genérica",
    "nulidad generica",
    "competencia territorial pura",
    "costas",
    "embargo patrimonial",
]
