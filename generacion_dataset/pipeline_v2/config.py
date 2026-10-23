"""Configuración del pipeline v2 de generación de datasets. Todo es sobrescribible por línea de comandos."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # generacion_dataset/
REPO = ROOT.parent                                   # peru-legal-rag-data/
SCRIPTS_V1 = ROOT / "scripts"                        # resolver y utilidades del pipeline anterior (se reutilizan)

# --- Insumos (los mismos que el pipeline v1) ---
# Fuente de verdad del corpus: la salida consolidada de la fase de recolección (no la copia de data/input, que puede quedar vieja).
CHUNKS_PATH = REPO / "recoleccion" / "data" / "processed" / "document_chunks_all.jsonl"
CASES_DIR = ROOT / "data" / "intermediate" / "resumeai_batch" / "cases"
CONTEXT_UNITS_PATH = ROOT / "data" / "input" / "jurisprudence_context_units.json"
_PROC = REPO / "recoleccion" / "data_types"
CP_ARTICLES_PATH = _PROC / "tipo_02_codigo_penal" / "data" / "processed" / "all_articles.json"
CPP_ARTICLES_PATH = _PROC / "tipo_03_codigo_procesal_penal" / "data" / "processed" / "all_articles.json"
LEY_30364_PATH = _PROC / "tipo_01_ley_30364" / "data" / "processed" / "law_30364_structured.json"
STRUCTURED_ENTRIES_PATH = _PROC / "tipo_04_jurisprudencia" / "data" / "processed" / "jurisprudence_entries_structured.json"

# --- Salidas ---
OUT_DIR = ROOT / "data" / "output" / "dataset_v2"

# --- Reproducibilidad ---
SEED = 520
PROMPT_VERSION = "v2-chunk-holdout-same-type-negatives-judged"

# --- Modelos (en modo "session" son informativos: quedan registrados en cada fila) ---
GENERATOR_MODEL = "anthropic/claude-sonnet-5.5"       # vía OpenRouter
JUDGE_MODEL = "anthropic/claude-sonnet-5.5"           # idealmente otro modelo/familia que el generador
GEN_TEMPERATURE = 0.4
JUDGE_TEMPERATURE = 0.0

# --- Partición por chunk (se decide ANTES de generar; es estable si el corpus cambia) ---
TEST_FRAC = 0.20
DEV_FRAC = 0.10
MIN_CHARS = 120        # chunks más cortos no generan preguntas útiles
MAX_CHARS = 8000       # chunks más largos se tratan como anómalos (revisar el parser) y se excluyen

# --- Cuántas preguntas por chunk / por caso ---
CHUNK_QUESTIONS = {"train": 6, "dev": 3, "test": 2}
CHUNKS_PER_TASK = 6                                   # chunks por llamada/archivo de tarea
CASE_QUESTIONS_MIN, CASE_QUESTIONS_MAX = 5, 10
CASE_MAX_CANDIDATES = 40                              # tope de candidatos mostrados al LLM por caso

# --- Calidad de las preguntas ---
MAX_LEXICAL_OVERLAP = 0.30    # fracción de palabras de contenido de la pregunta presentes en el positivo
                              # (set original unseen: media 0.27; preguntas reales de casos: 0.12; reformulado: 0.08)
NEAR_DUP_JACCARD = 0.80
QUERY_MIN_CHARS, QUERY_MAX_CHARS = 40, 230

# --- Negativos ---
N_NEG_SELECT = 12              # negativos elegidos por pregunta (se juzgan y se descartan los dudosos)
N_NEG_FINAL = 10               # negativos por fila de entrenamiento: train_group_size 11 = 1 positivo + 10 negativos (como el training.json actual)
BM25_DEPTH = 300
MAX_NEG_USES = 150             # un mismo chunk no puede ser negativo en más de N preguntas (evita "chunks imán"; el promedio esperado es ~70)
CASE_CANDIDATE_NEGS = 0        # candidatos del caso NO elegidos como positivos usados como negativos. 0 tras el piloto: 44 % eran
                               # 'parcial' y 3 % 'si' según el juez (son los peores negativos posibles)
NEG_MIN_RANK = 5               # no usar los 5 primeros del BM25 como negativos: en el piloto 17 % eran 'si' y 17 % 'parcial'
NEG_MAX_SCORE_RATIO = 0.9      # ni negativos con puntaje BM25 >= 90 % del mejor positivo (minería sensible al positivo)
SIBLING_NEG_EXCLUSION = True   # excluye 22-A / 22-B cuando el positivo es el 22 (suelen responder lo mismo)

# --- Verificación independiente (juez) ---
JUDGE_QUESTIONS_PER_TASK = 5
NEG_JUDGE_FRACTION = 0.25      # fracción de preguntas de entrenamiento cuyos negativos se juzgan todos
                               # (los negativos que provienen de candidatos del caso se juzgan siempre)
JUDGE_TEXT_CHARS = 8000        # el juez lee el chunk completo (los chunks del corpus corregido miden <= 7.600 caracteres)

# --- Armado final ---
MAX_ROWS_PER_POSITIVE = 12     # tope de filas de entrenamiento por chunk positivo
MAX_TYPE_AUC = 0.55            # el tipo de fuente no debe predecir la etiqueta (positivo vs negativo)
MIN_ROWS_FOR_AUC_CHECK = 500   # con menos filas el AUC es ruido: solo se informa
MAX_FALSE_NEGATIVE_SI_RATE = 0.08   # tasa máxima de negativos que el juez marca 'si' (los 'parcial' no cuentan como falso negativo)
FINETUNING_PROMPT = "Represent this sentence for searching relevant passages: "

TOPICS = [
    "identificacion_delito", "canales_denuncia", "medidas_proteccion", "hijos_y_tenencia",
    "pruebas_y_certificados", "lesiones_secuelas_indemnizacion", "violencia_psicologica", "violencia_fisica",
    "violencia_economica", "violencia_sexual", "procedimiento_penal", "desconfianza_en_justicia",
    "reparacion_civil", "sancion_penal_al_agresor", "doctrina_jurisprudencial", "otro",
]
BARRIERS = [
    "verguenza", "desconocimiento_derechos", "no_sabe_como_denunciar", "desconfianza_sistema", "miedo_agresor",
    "dependencia_economica", "preocupacion_hijos", "duda_si_es_delito", "otro",
]
