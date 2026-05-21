"""
processor.py
------------
Limpieza, deduplicación, scoring y filtros de privacidad.
Opera sobre los resultados crudos de searcher.py.
Sin base de datos: todo en memoria.
"""

import re
import logging
from rapidfuzz import fuzz

log = logging.getLogger(__name__)

# Patrones de datos privados que el agente NUNCA debe incluir en el reporte
_PATRONES_PRIVADOS = [
    r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b",          # emails
    r"\b(\+?\d[\s\-.]?){7,15}\b",               # teléfonos
    r"\b\d{6,}\b",                               # números largos (documentos)
    r"contraseña|password|clave|token|api.?key", # credenciales
]


# ---------------------------------------------------------------------------
# 1. Deduplicación por URL
# ---------------------------------------------------------------------------

def deduplicate_results(results: list[dict]) -> list[dict]:
    """Elimina resultados con URL duplicada. Mantiene el primero visto."""
    seen = set()
    unique = []
    for r in results:
        url = r.get("url", "").strip().rstrip("/")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)
    log.info(f"[PROC] Deduplicación: {len(results)} → {len(unique)} resultados")
    return unique


# ---------------------------------------------------------------------------
# 2. Scoring de relevancia por similitud de nombre
# ---------------------------------------------------------------------------

def score_by_name_similarity(results: list[dict], name: str) -> list[dict]:
    """
    Asigna un score 0-100 a cada resultado basado en cuánto
    coincide el nombre buscado con el contenido encontrado.
    Usa RapidFuzz para comparación fuzzy (tolerante a variantes).
    """
    name_lower = name.lower()

    for r in results:
        texto = f"{r.get('titulo','')} {r.get('snippet','')}".lower()

        # Coincidencia exacta del nombre completo
        score_exact = fuzz.partial_ratio(name_lower, texto)

        # Coincidencia de partes del nombre (nombre y apellido por separado)
        partes = name_lower.split()
        score_partes = min(
            fuzz.partial_ratio(parte, texto) for parte in partes
        ) if partes else 0

        # Score final: promedio ponderado
        score_final = int(score_exact * 0.7 + score_partes * 0.3)

        # Bonus si la URL también contiene el nombre
        url_lower = r.get("url", "").lower()
        nombre_url = name_lower.replace(" ", "").replace("-", "")
        if any(p in url_lower for p in partes):
            score_final = min(100, score_final + 10)

        r["score"] = score_final
        r["confianza"] = _score_a_nivel(score_final)

    # Ordenar de mayor a menor score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def _score_a_nivel(score: int) -> str:
    """Convierte score numérico a nivel legible."""
    if score >= 80:
        return "alta"
    elif score >= 55:
        return "media"
    else:
        return "baja"


# ---------------------------------------------------------------------------
# 3. Filtro de privacidad (obligatorio — nunca omitir)
# ---------------------------------------------------------------------------

def filter_private_data(results: list[dict]) -> list[dict]:
    """
    Elimina o censura datos privados de cada resultado.
    Emails, teléfonos, documentos de identidad, credenciales.
    """
    filtrados = []
    for r in results:
        snippet = r.get("snippet", "")
        contiene_dato_privado = False

        for patron in _PATRONES_PRIVADOS:
            if re.search(patron, snippet, re.IGNORECASE):
                # Censurar en lugar de eliminar, para trazabilidad
                snippet = re.sub(patron, "[DATO PRIVADO OMITIDO]", snippet, flags=re.IGNORECASE)
                contiene_dato_privado = True

        r["snippet"] = snippet
        r["contiene_dato_privado"] = contiene_dato_privado
        filtrados.append(r)

    censurados = sum(1 for r in filtrados if r.get("contiene_dato_privado"))
    if censurados:
        log.info(f"[PRIVACIDAD] Se censuraron datos en {censurados} resultados")
    return filtrados


# ---------------------------------------------------------------------------
# 4. Detección de homonimia
# ---------------------------------------------------------------------------

def detect_homonyms(results: list[dict], name: str) -> list[dict]:
    """
    Detecta resultados que probablemente corresponden a una persona diferente
    con el mismo nombre. Usa señales de contexto para marcarlos.
    """
    # Señales que sugieren contexto diferente al esperado
    señales_conflicto = [
        "contador", "abogado", "médico", "político", "artista",
        "actor", "futbolista", "cantante", "músico", "chef",
        "arquitecto", "empresario", "periodista",
    ]

    for r in results:
        texto = f"{r.get('titulo','')} {r.get('snippet','')}".lower()
        conflictos = [s for s in señales_conflicto if s in texto]

        r["posible_homonimo"] = len(conflictos) >= 2
        r["señales_homonimo"] = conflictos

    homonimos = sum(1 for r in results if r.get("posible_homonimo"))
    if homonimos:
        log.info(f"[HOMONIMIA] {homonimos} resultados marcados como posible homonimia")
    return results


# ---------------------------------------------------------------------------
# 5. Filtrar por score mínimo
# ---------------------------------------------------------------------------

def filter_by_score(results: list[dict], min_score: int = 40) -> list[dict]:
    """Descarta resultados con score menor al umbral."""
    filtrados = [r for r in results if r.get("score", 0) >= min_score]
    descartados = len(results) - len(filtrados)
    if descartados:
        log.info(f"[PROC] Descartados {descartados} resultados bajo score mínimo ({min_score})")
    return filtrados


# ---------------------------------------------------------------------------
# Función principal: pipeline completo de procesamiento
# ---------------------------------------------------------------------------

def procesar(resultados_crudos: dict[str, list[dict]], name: str, min_score: int = 40) -> list[dict]:
    """
    Pipeline completo:
    1. Aplanar todas las fuentes en una sola lista
    2. Deduplicar
    3. Filtrar datos privados
    4. Calcular scores
    5. Detectar homonimia
    6. Filtrar por score mínimo
    """
    # 1. Aplanar
    todos = []
    for fuente, lista in resultados_crudos.items():
        todos.extend(lista)

    log.info(f"[PROC] Total resultados crudos: {len(todos)}")

    # 2. Deduplicar
    todos = deduplicate_results(todos)

    # 3. Filtrar datos privados (siempre primero)
    todos = filter_private_data(todos)

    # 4. Scoring
    todos = score_by_name_similarity(todos, name)

    # 5. Homonimia
    todos = detect_homonyms(todos, name)

    # 6. Filtrar irrelevantes
    todos = filter_by_score(todos, min_score=min_score)

    log.info(f"[PROC] Resultados finales procesados: {len(todos)}")
    return todos
