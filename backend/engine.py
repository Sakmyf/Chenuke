"""Motor de análisis contextual — SignalCheck v15.16-clean.

Orquesta los módulos de análisis individuales, compone el risk score
y devuelve un resultado unificado con signals, nivel y métricas pro.
"""

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from backend.Analysis.credibility import analyze as analyze_credibility
from backend.Analysis.contradictions import analyze_contradictions
from backend.Analysis.authority import analyze_authority
from backend.Analysis.urgency import check_urgency
from backend.Analysis.emotions import analyze as check_emotions
from backend.Analysis.polarization import check_polarization
from backend.Analysis.misinformation import check_misinformation
from backend.Analysis.scientific_claims import check_scientific_claims
from backend.Analysis.narrative_patterns import analyze as analyze_narrative_patterns
from backend.Analysis.hypothetical import check_hypothetical
from backend.Analysis.promises import check_promises
from backend.Analysis.detect_uncertainty import detect_uncertainty
from backend.Analysis.commercial_risk import analyze_commercial_risk
from backend.Analysis.structural import check_structural
from backend.source_analyzer import analyze_source
from backend.context_classifier import classify_context
from backend.weight_engine import adjust_weights
from backend.confidence_score import compute_confidence

logger = logging.getLogger(__name__)

ENGINE_VERSION = "15.16-clean"

# ---------------------------------------------------------------------------
# Configuración de pesos base
# ---------------------------------------------------------------------------
BASE_WEIGHTS: dict[str, float] = {
    "credibility": 0.10, "contradictions": 0.07, "authority": 0.08,
    "urgency": 0.10, "emotions": 0.09, "polarization": 0.10,
    "misinformation": 0.12, "scientific_claims": 0.08,
    "narrative_patterns": 0.08, "hypothetical": 0.05,
    "promises": 0.10, "uncertainty": 0.13, "structural": 0.10,
}

# ---------------------------------------------------------------------------
# Umbrales y constantes tuneables
# ---------------------------------------------------------------------------
MIN_CHARS_FOR_STRUCTURAL = 280
MAX_SIGNALS = 6
MODULE_TIMEOUT_SECONDS = 2.0
POOL_WORKERS = 13

# Pisos de riesgo para señales críticas (no deben promediarse)
FLOOR_WEALTH_LURE = 0.60
FLOOR_COMMERCIAL_HIGH = 0.62

# Descuentos de autoridad por tipo de fuente
INSTITUTIONAL_DOMAIN_DISCOUNT = 0.12
INSTITUTIONAL_DOMAIN_AUTHORITY_FACTOR = 0.8
INSTITUTIONAL_CONTEXT_AUTHORITY_FACTOR = 0.5
DEFAULT_AUTHORITY_FACTOR = 0.25
MAX_AUTHORITY_BONUS = 0.15

# Riesgo comercial
MAX_COMMERCIAL_WEIGHT = 0.20
COMMERCIAL_SCORE_FACTOR = 0.4

# Niveles de riesgo
RISK_LEVEL_HIGH = 0.60
RISK_LEVEL_MEDIUM = 0.20

# Señal de fraude por enriquecimiento (debe coincidir con backend.Analysis.promises)
WEALTH_LURE_SIGNAL = "wealth_lure_pattern"

# Nivel mínimo de alarma para texto breve
SHORT_TEXT_ALARM_THRESHOLD = 0.4

# ---------------------------------------------------------------------------
# Labels de señales (mapa de códigos internos → texto legible)
# ---------------------------------------------------------------------------
SIGNAL_LABELS: dict[str, str] = {
    "urgency_pressure": "Presión de urgencia artificial",
    "manipulación_emocional": "Manipulación emocional",
    "exaggerated_promises": "Promesas absolutas o garantías exageradas",
    "polarization_detected": "Lenguaje polarizador",
    "overgeneralization": "Generalizaciones absolutas",
    "serious_accusation_without_source": "Acusación grave sin fuente visible",
    "conspiracy_language": "Lenguaje conspirativo",
    "categorical_claim": "Afirmación categórica fuerte",
    "unsupported_scientific_claim": "Afirmación científica/salud sin respaldo visible",
    "multiple_health_claims_with_partial_support": "Múltiples afirmaciones de salud con respaldo parcial",
    "conspiracy_narrative": "Narrativa conspirativa",
    "dramatized_structure": "Estructura dramatizada",
    "unverified_reconstruction": "Reconstrucción no verificable",
    "fictional_narrative_with_real_context": "Narrativa ficticia aplicada a contexto real",
    "hypothetical_or_unverified_claim": "Lenguaje hipotético presentado como hecho",
    "numbers_without_strong_source": "Datos numéricos sin fuente sólida",
    "excessive_conditional_language": "Uso excesivo de condicionales",
    "unverified_categorical_claim": "Afirmación categórica sin respaldo",
    "recent_unattributed_claim": "Hecho reciente sin atribución clara",
    "title_body_gap": "Desfase entre titular y contenido",
    "internal_contradiction": "Contradicción interna detectada",
    "weak_authority": "Autoridad difusa sin referente concreto",
    "absolute_generalization": "Generalización absoluta desproporcionada",
    "clickbait_structure": "Estructura tipo clickbait",
    "excessive_uppercase": "Uso excesivo de mayúsculas",
}

# ---------------------------------------------------------------------------
# Pool de hilos compartido (se crea una sola vez, vive toda la vida del proceso)
# ---------------------------------------------------------------------------
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=POOL_WORKERS, thread_name_prefix="signalcheck")
        logger.debug("ThreadPoolExecutor creado (%d workers)", POOL_WORKERS)
    return _executor


# ---------------------------------------------------------------------------
# Módulos de análisis: mapeo nombre → (función, args_extra)
# ---------------------------------------------------------------------------
ANALYSIS_MODULES: dict[str, tuple] = {
    "credibility": (analyze_credibility, ("text",)),
    "contradictions": (analyze_contradictions, ("text",)),
    "authority": (analyze_authority, ("text",)),
    "urgency": (check_urgency, ("text",)),
    "emotions": (check_emotions, ("text",)),
    "polarization": (check_polarization, ("text",)),
    "misinformation": (check_misinformation, ("text",)),
    "scientific_claims": (check_scientific_claims, ("text",)),
    "narrative_patterns": (analyze_narrative_patterns, ("text",)),
    "hypothetical": (check_hypothetical, ("text",)),
    "promises": (check_promises, ("text",)),
    "uncertainty": (detect_uncertainty, ("text", "title", "context")),
    "structural": (check_structural, ("text",)),
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def normalize_result(res: Any) -> dict:
    """Normaliza el output de cualquier módulo a un dict con estructura uniforme."""
    if res is None:
        return {"score": 0.0, "reasons": [], "evidence": [], "trust_bonus": 0.0}
    if isinstance(res, dict):
        return {
            "score": float(res.get("score", 0.0) or 0.0),
            "reasons": res.get("reasons") or res.get("signals") or [],
            "evidence": res.get("evidence") or res.get("signals") or [],
            "trust_bonus": float(res.get("trust_bonus", 0.0) or 0.0),
        }
    # Objeto tipo dataclass / NamedTuple
    return {
        "score": float(getattr(res, "points", 0.0) or 0.0),
        "reasons": getattr(res, "reasons", []) or [],
        "evidence": getattr(res, "evidence", []) or [],
        "trust_bonus": float(getattr(res, "trust_bonus", 0.0) or 0.0),
    }


def _get_score(result: Any) -> float:
    """Extrae el score normalizado de un resultado, clamped a [0, 1]."""
    return max(0.0, min(normalize_result(result)["score"], 1.0))


def _is_commercial_alarm(comm_data: dict) -> bool:
    return comm_data.get("level") in ("medio", "alto")


# ---------------------------------------------------------------------------
# Mapeo riesgo → score 0-100 (amplificación no-lineal)
# ---------------------------------------------------------------------------
_SCORE_ANCHORS = [(0.0, 0), (0.10, 22), (0.25, 50), (0.50, 75), (1.0, 100)]


def _map_risk_to_score(risk: float) -> int:
    risk = max(0.0, min(risk, 1.0))
    for (x0, y0), (x1, y1) in zip(_SCORE_ANCHORS, _SCORE_ANCHORS[1:]):
        if risk <= x1:
            return int(round(y0 + (risk - x0) * (y1 - y0) / (x1 - x0)))
    return 100


# ---------------------------------------------------------------------------
# Recolección de señales
# ---------------------------------------------------------------------------
def _collect_signals(module_results: dict, max_signals: int = MAX_SIGNALS) -> list:
    """Recopila las señales más relevantes de todos los módulos, sin duplicados."""
    signals: list[dict] = []
    seen: set[str] = set()
    for module_name, result in module_results.items():
        n = normalize_result(result)
        if not n["reasons"] and n["score"] < 0.05:
            continue
        for reason in n["reasons"]:
            if reason in seen:
                continue
            seen.add(reason)
            signals.append({
                "label": SIGNAL_LABELS.get(reason, str(reason).replace("_", " ").capitalize()),
                "detail": n["evidence"][0] if n["evidence"] else "",
                "module": module_name,
            })
            if len(signals) >= max_signals:
                return signals
    return signals


# ---------------------------------------------------------------------------
# Ejecución paralela de módulos
# ---------------------------------------------------------------------------
def _run_modules(
    text: str, title: str, context: str, url: str
) -> dict[str, Any]:
    """Ejecuta todos los módulos de análisis en paralelo y devuelve sus resultados."""
    arg_map = {"text": text, "title": title, "context": context, "url": url}
    executor = _get_executor()
    results: dict[str, Any] = {}

    # Lanzar módulos principales
    futures: dict[str, Any] = {}
    for name, (func, arg_keys) in ANALYSIS_MODULES.items():
        args = [arg_map[k] for k in arg_keys]
        futures[name] = executor.submit(func, *args)

    # Lanzar análisis comercial (usa args distintos)
    futures["commercial_risk"] = executor.submit(analyze_commercial_risk, text, url, context)

    # Recoger resultados
    for name, future in futures.items():
        try:
            results[name] = future.result(timeout=MODULE_TIMEOUT_SECONDS)
        except Exception as exc:
            logger.warning("Módulo %s falló: %s", name, exc)
            results[name] = None

    return results


# ---------------------------------------------------------------------------
# Composición del risk score
# ---------------------------------------------------------------------------
def _compose_risk_score(
    scores: dict[str, float],
    weights: dict[str, float],
    results: dict[str, Any],
    source_info: dict,
) -> float:
    """Compone el risk score ponderado + ajustes de autoridad y comercial."""
    # Score estructural ponderado
    structural_score = sum(
        scores[k] * weights.get(k, 0.1) for k in scores
    )

    # Componente comercial (capado)
    comm_data = results.get("commercial_risk") or {"score": 0}
    commercial_score = min(
        MAX_COMMERCIAL_WEIGHT,
        (comm_data.get("score", 0) / 10) * COMMERCIAL_SCORE_FACTOR,
    )

    risk_score = structural_score + commercial_score

    # Descuento por autoridad verificada
    authority_bonus = min(normalize_result(results.get("authority"))["trust_bonus"], MAX_AUTHORITY_BONUS)
    source_type = source_info.get("type", "")

    if source_type == "institutional":
        risk_score = max(0.0, risk_score - INSTITUTIONAL_DOMAIN_DISCOUNT)
        risk_score -= authority_bonus * INSTITUTIONAL_DOMAIN_AUTHORITY_FACTOR
    else:
        # Se usaría context aquí si estuviera disponible; por ahora default
        risk_score -= authority_bonus * DEFAULT_AUTHORITY_FACTOR

    risk_score = max(0.0, min(risk_score, 1.0))
    return risk_score


def _apply_floors(risk_score: float, results: dict, comm_data: dict) -> float:
    """Aplica pisos de riesgo para señales críticas de fraude."""
    promises_reasons = normalize_result(results.get("promises"))["reasons"]
    if WEALTH_LURE_SIGNAL in promises_reasons:
        risk_score = max(risk_score, FLOOR_WEALTH_LURE)
    if comm_data.get("level") == "alto":
        risk_score = max(risk_score, FLOOR_COMMERCIAL_HIGH)
    return risk_score


def _compute_level(risk_normalized: float) -> tuple[str, str]:
    """Devuelve (level, message) según el riesgo normalizado."""
    if risk_normalized >= RISK_LEVEL_HIGH:
        return "alto", "Presión narrativa significativa detectada"
    if risk_normalized >= RISK_LEVEL_MEDIUM:
        return "medio", "Señales mixtas — lectura crítica recomendada"
    return "bajo", "Bajo riesgo estructural detectado"


def _build_pro_metrics(scores: dict[str, float]) -> dict:
    """Construye las métricas visibles para usuarios pro."""
    return {
        "emocionalidad": int(max(scores.get("emotions", 0), scores.get("polarization", 0)) * 100),
        "manipulacion": int(max(
            scores.get("urgency", 0),
            scores.get("promises", 0),
            scores.get("narrative_patterns", 0),
        ) * 100),
        "evidencia": int(max(0, 100 - scores.get("uncertainty", 0) * 100)),
        "coherencia": int(max(0, 100 - scores.get("contradictions", 0) * 100)),
    }


# ---------------------------------------------------------------------------
# Manojo de texto breve
# ---------------------------------------------------------------------------
def _short_text_response(
    text: str,
    scores: dict[str, float],
    results: dict,
    comm_data: dict,
    context: str,
    source_info: dict,
) -> dict | None:
    """Si el texto es muy corto, devuelve una respuesta de abstención o alerta.
    Devuelve None si el texto es suficiente para análisis completo."""
    clean_len = len((text or "").strip())
    if clean_len >= MIN_CHARS_FOR_STRUCTURAL:
        return None

    # ¿Hay señales de alarma pese a ser corto?
    alarm = max(
        scores.get("urgency", 0),
        scores.get("promises", 0),
        scores.get("narrative_patterns", 0),
        scores.get("emotions", 0),
    )
    commercial_alarm = _is_commercial_alarm(comm_data)

    if alarm < SHORT_TEXT_ALARM_THRESHOLD and not commercial_alarm:
        return {
            "score": None,
            "level": "insuficiente",
            "message": "Texto insuficiente para análisis estructural",
            "insight": (
                "El contenido es demasiado corto para evaluar de forma confiable "
                "cómo está construido el mensaje. SignalCheck se abstiene en vez de "
                "dar un resultado injustificado."
            ),
            "signals": [],
            "confidence": None,
            "context": context,
            "source_type": source_info.get("type", "unknown"),
            "commercial_risk": comm_data,
            "engine_version": ENGINE_VERSION,
            "pro": {},
        }

    # Alerta cualitativa — hay señales de presión en texto breve
    signals_short = _collect_signals(
        {k: results[k] for k in results if k != "commercial_risk"}
    )
    if commercial_alarm:
        signals_short.append({
            "label": "Riesgo comercial",
            "detail": comm_data.get("summary", ""),
            "module": "commercial_risk",
        })

    return {
        "score": None,
        "level": "alerta_breve",
        "message": "Texto breve con señales de presión — precaución",
        "insight": (
            "El contenido es demasiado corto para un análisis estructural completo, "
            "pero se detectaron señales de presión o manipulación. Leé con cautela."
        ),
        "signals": signals_short[:MAX_SIGNALS],
        "confidence": None,
        "context": context,
        "source_type": source_info.get("type", "unknown"),
        "commercial_risk": comm_data,
        "engine_version": ENGINE_VERSION,
        "pro": {},
    }


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def analyze_context(
    text: str,
    url: str = "",
    title: str = "",
    is_ecommerce: bool = False,
) -> dict:
    """Punto de entrada del motor de análisis.

    Orquesta todos los módulos, compone el risk score y devuelve
    un resultado unificado con signals, nivel, confianza y métricas.
    """
    try:
        # --- Guard: texto vacío ---
        if not text:
            return {
                "score": 0, "level": "bajo",
                "message": "Sin contenido para analizar",
                "signals": [], "confidence": 0,
                "engine_version": ENGINE_VERSION,
            }

        # --- Contexto y fuente ---
        context = classify_context(text, url)
        if is_ecommerce and context == "general":
            context = "ecommerce"
        source_info = analyze_source(url, text)

        # --- Pesos ajustados al contexto ---
        weights = adjust_weights(BASE_WEIGHTS, context, source_info)

        # --- Ejecutar módulos en paralelo ---
        results = _run_modules(text, title, context, url)

        # --- Scores normalizados por módulo ---
        scores = {k: _get_score(results[k]) for k in BASE_WEIGHTS}

        # --- Componer risk score ---
        risk_score = _compose_risk_score(scores, weights, results, source_info)
        comm_data = results.get("commercial_risk") or {"score": 0}
        risk_score = _apply_floors(risk_score, results, comm_data)

        final_score = _map_risk_to_score(risk_score)
        normalized_risk = final_score / 100

        # --- Texto breve: abstención o alerta ---
        short_response = _short_text_response(
            text, scores, results, comm_data, context, source_info
        )
        if short_response is not None:
            return short_response

        # --- Nivel y mensaje ---
        level, message = _compute_level(normalized_risk)

        # --- Señales ---
        module_results = {k: results[k] for k in results if k != "commercial_risk"}
        signals = _collect_signals(module_results)
        if _is_commercial_alarm(comm_data):
            signals.append({
                "label": "Riesgo comercial",
                "detail": comm_data.get("summary", ""),
                "module": "commercial_risk",
            })
            signals = signals[:MAX_SIGNALS]

        return {
            "score": final_score,
            "level": level,
            "message": message,
            "signals": signals,
            "confidence": compute_confidence(scores),
            "context": context,
            "source_type": source_info.get("type", "unknown"),
            "commercial_risk": comm_data,
            "engine_version": ENGINE_VERSION,
            "pro": {"metrics": _build_pro_metrics(scores)},
        }

    except Exception as e:
        logger.exception("Error en analyze_context")
        return {
            "score": 0, "level": "medio",
            "message": "Error en el motor",
            "signals": [{"label": "engine_error", "detail": str(e), "module": "engine"}],
            "confidence": 0,
            "engine_version": ENGINE_VERSION,
        }