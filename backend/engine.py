import traceback
from concurrent.futures import ThreadPoolExecutor

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

ENGINE_VERSION = "15.9-clean"

BASE_WEIGHTS = {
    "credibility": 0.10, "contradictions": 0.07, "authority": 0.08,
    "urgency": 0.10, "emotions": 0.09, "polarization": 0.10,
    "misinformation": 0.12, "scientific_claims": 0.08,
    "narrative_patterns": 0.08, "hypothetical": 0.05,
    "promises": 0.10, "uncertainty": 0.13, "structural": 0.10,
}

SIGNAL_LABELS = {
    "urgency_pressure": "Presión de urgencia artificial",
    "manipulación emocional": "Manipulación emocional",
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

def normalize_result(res):
    if res is None:
        return {"score": 0.0, "reasons": [], "evidence": [], "trust_bonus": 0.0}
    if isinstance(res, dict):
        return {
            "score": float(res.get("score", 0.0) or 0.0),
            "reasons": res.get("reasons") or res.get("signals") or [],
            "evidence": res.get("evidence") or res.get("signals") or [],
            "trust_bonus": float(res.get("trust_bonus", 0.0) or 0.0),
        }
    return {
        "score": float(getattr(res, "points", 0.0) or 0.0),
        "reasons": getattr(res, "reasons", []) or [],
        "evidence": getattr(res, "evidence", []) or [],
        "trust_bonus": float(getattr(res, "trust_bonus", 0.0) or 0.0),
    }

def _get_score(result):
    return max(0.0, min(normalize_result(result)["score"], 1.0))

def _collect_signals(module_results: dict) -> list:
    signals = []; seen = set()
    for module_name, result in module_results.items():
        n = normalize_result(result)
        if not n["reasons"] and n["score"] < 0.05: continue
        for reason in n["reasons"]:
            if reason in seen: continue
            seen.add(reason)
            signals.append({
                "label": SIGNAL_LABELS.get(reason, str(reason).replace("_", " ").capitalize()),
                "detail": n["evidence"][0] if n["evidence"] else "",
                "module": module_name,
            })
            if len(signals) >= 6: return signals
    return signals

# Mapeo monotónico riesgo→score (interpolación lineal entre anclas).
# Amplifica el rango bajo sin invertir el orden: más riesgo => siempre más score.
_SCORE_ANCHORS = [(0.0, 0), (0.10, 22), (0.25, 50), (0.50, 75), (1.0, 100)]

def _map_risk_to_score(risk: float) -> int:
    risk = max(0.0, min(risk, 1.0))
    for (x0, y0), (x1, y1) in zip(_SCORE_ANCHORS, _SCORE_ANCHORS[1:]):
        if risk <= x1:
            return int(round(y0 + (risk - x0) * (y1 - y0) / (x1 - x0)))
    return 100

def analyze_context(text: str, url: str = "", title: str = "", is_ecommerce: bool = False):
    try:
        if not text:
            return {"score": 0, "level": "bajo", "message": "Sin contenido para analizar", "signals": [], "confidence": 0, "engine_version": ENGINE_VERSION}
        context = classify_context(text, url)
        if is_ecommerce and context == "general":
            context = "ecommerce"
        source_info = analyze_source(url, text)
        weights = adjust_weights(BASE_WEIGHTS, context, source_info)
        with ThreadPoolExecutor(max_workers=13) as executor:
            futures = {
                "credibility": executor.submit(analyze_credibility, text),
                "contradictions": executor.submit(analyze_contradictions, text),
                "authority": executor.submit(analyze_authority, text),
                "urgency": executor.submit(check_urgency, text),
                "emotions": executor.submit(check_emotions, text),
                "polarization": executor.submit(check_polarization, text),
                "misinformation": executor.submit(check_misinformation, text),
                "scientific_claims": executor.submit(check_scientific_claims, text),
                "narrative_patterns": executor.submit(analyze_narrative_patterns, text),
                "hypothetical": executor.submit(check_hypothetical, text),
                "promises": executor.submit(check_promises, text),
                "uncertainty": executor.submit(detect_uncertainty, text, title, context),
                "structural": executor.submit(check_structural, text),
                "commercial_risk": executor.submit(analyze_commercial_risk, text, url),
            }
            results = {}
            for name, future in futures.items():
                try:
                    results[name] = future.result(timeout=2.0)
                except Exception:
                    traceback.print_exc()
                    results[name] = None
        scores = {k: _get_score(results[k]) for k in BASE_WEIGHTS.keys()}
        structural_score = sum(scores[k] * weights.get(k, 0.1) for k in scores)
        comm_data = results["commercial_risk"] or {"score": 0}
        commercial_score = min(0.20, (comm_data.get("score", 0) / 10) * 0.4)
        risk_score = structural_score + commercial_score
        authority_bonus = min(normalize_result(results["authority"])["trust_bonus"], 0.15)
        if source_info.get("type") == "institutional": risk_score -= authority_bonus * 0.8
        elif context == "institutional": risk_score -= authority_bonus * 0.5
        else: risk_score -= authority_bonus * 0.25
        risk_score = max(0.0, min(risk_score, 1.0))

        # --- Piso de riesgo para señales CRÍTICAS de fraude ---
        # Algunas señales no deben promediarse: una promesa de enriquecimiento o un
        # pedido de transferencia son de alto riesgo POR SÍ SOLAS, aunque el resto
        # del texto sea sobrio. Sin esto, un scam "prolijo" (sin urgencia chillona)
        # se diluye entre 12 módulos que dan 0. El piso garantiza que estas señales
        # lleguen al usuario como riesgo significativo. (Mismo principio que ya rige
        # para commercial_risk, generalizado a la promesa de enriquecimiento.)
        promises_reasons = normalize_result(results.get("promises"))["reasons"]
        if "wealth_lure_pattern" in promises_reasons:
            risk_score = max(risk_score, 0.60)   # piso → rojo: scam de inversión confirmado
        if comm_data.get("level") == "alto":
            risk_score = max(risk_score, 0.62)   # piso → rojo: pedido de pago/datos

        final_score = _map_risk_to_score(risk_score)
        normalized_risk = final_score / 100

        # --- Texto insuficiente para análisis estructural (honestidad epistémica) ---
        # Un texto muy corto no da material para evaluar CÓMO está construido el
        # mensaje. En vez de inventar un score sobre poca evidencia, se abstiene.
        # EXCEPCIÓN (opción B): si pese a ser corto hay señales fuertes de presión
        # (urgencia, promesas, manipulación, riesgo comercial), se emite una ALERTA
        # cualitativa —no un score— para proteger al usuario de estafas breves.
        MIN_CHARS_FOR_STRUCTURAL = 280
        clean_len = len((text or "").strip())
        if clean_len < MIN_CHARS_FOR_STRUCTURAL:
            alarm = max(
                scores.get("urgency", 0), scores.get("promises", 0),
                scores.get("narrative_patterns", 0), scores.get("emotions", 0),
            )
            commercial_alarm = comm_data.get("level") in ("medio", "alto")
            if alarm >= 0.4 or commercial_alarm:
                signals_short = _collect_signals({k: results[k] for k in results if k != "commercial_risk"})
                if commercial_alarm:
                    signals_short.append({"label": "Riesgo comercial", "detail": comm_data.get("summary", ""), "module": "commercial_risk"})
                return {
                    "score": None, "level": "alerta_breve",
                    "message": "Texto breve con señales de presión — precaución",
                    "insight": "El contenido es demasiado corto para un análisis estructural completo, pero se detectaron señales de presión o manipulación. Leé con cautela.",
                    "signals": signals_short[:6], "confidence": None,
                    "context": context, "source_type": source_info.get("type", "unknown"),
                    "commercial_risk": comm_data, "engine_version": ENGINE_VERSION, "pro": {},
                }
            return {
                "score": None, "level": "insuficiente",
                "message": "Texto insuficiente para análisis estructural",
                "insight": "El contenido es demasiado corto para evaluar de forma confiable cómo está construido el mensaje. SignalCheck se abstiene en vez de dar un resultado injustificado.",
                "signals": [], "confidence": None,
                "context": context, "source_type": source_info.get("type", "unknown"),
                "commercial_risk": comm_data, "engine_version": ENGINE_VERSION, "pro": {},
            }

        if normalized_risk >= 0.60:
            level = "alto"; message = "Presión narrativa significativa detectada"
        elif normalized_risk >= 0.20:
            level = "medio"; message = "Señales mixtas — lectura crítica recomendada"
        else:
            level = "bajo"; message = "Bajo riesgo estructural detectado"
        module_results = {k: results[k] for k in results if k != "commercial_risk"}
        signals = _collect_signals(module_results)
        if comm_data.get("level") in ("medio", "alto"):
            signals.append({"label": "Riesgo comercial", "detail": comm_data.get("summary", ""), "module": "commercial_risk"})
            signals = signals[:6]
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
            "pro": {"metrics": {
                "emocionalidad": int(max(scores.get("emotions", 0), scores.get("polarization", 0)) * 100),
                "manipulacion": int(max(scores.get("urgency", 0), scores.get("promises", 0), scores.get("narrative_patterns", 0)) * 100),
                "evidencia": int(max(0, 100 - scores.get("uncertainty", 0) * 100)),
                "coherencia": int(max(0, 100 - scores.get("contradictions", 0) * 100)),
            }}
        }
    except Exception as e:
        traceback.print_exc()
        return {"score": 0, "level": "medio", "message": "Error en el motor", "signals": [{"label": "engine_error", "detail": str(e), "module": "engine"}], "confidence": 0, "engine_version": ENGINE_VERSION}
