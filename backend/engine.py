import re
import traceback
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

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


ENGINE_VERSION = "15.23-landing-shield"


BASE_WEIGHTS = {
    "credibility": 0.10,
    "contradictions": 0.07,
    "authority": 0.08,
    "urgency": 0.10,
    "emotions": 0.09,
    "polarization": 0.10,
    "misinformation": 0.12,
    "scientific_claims": 0.08,
    "narrative_patterns": 0.08,
    "hypothetical": 0.05,
    "promises": 0.10,
    "uncertainty": 0.13,
    "structural": 0.10,
}


SIGNAL_LABELS = {
    "urgency_pressure": "Presión de urgencia artificial",
    "manipulación emocional": "Manipulación emocional",
    "exaggerated_promises": "Promesas absolutas o garantías exageradas",
    "wealth_lure_pattern": "Promesa de ganancia o enriquecimiento",
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


NEWS_CONTEXTS = {
    "news",
    "news_media",
    "politics",
    "opinion",
}

INSTITUTIONAL_TYPES = {
    "institutional",
    "government",
    "education",
    "official",
}

NEWS_DOMAINS = (
    "cronista.com",
    "cronica.com.ar",
    "lavoz.com.ar",
    "iprofesional.com",
    "clarin.com",
    "lanacion.com",
    "infobae.com",
    "pagina12.com.ar",
    "ambito.com",
    "perfil.com",
)


LANDING_CTA_RE = re.compile(
    r"registrate ahora"
    r"|regístrate ahora"
    r"|solicitar información"
    r"|aprenda a negociar"
    r"|aprend[eé]\s+y\s+gan[aá]"
    r"|aprend[eé]\s+trading"
    r"|aprend[eé]\s+a\s+operar"
    r"|inicia\s+tu\s+camino"
    r"|empez[aá]\s+ahora"
    r"|comenz[aá]\s+ahora"
    r"|prefiero\s+operar"
    r"|me\s+mola\s+el\s+trading"
    r"|unite\s+ahora"
    r"|sumate",
    re.IGNORECASE,
)

FORM_RE = re.compile(
    r"\bnombre\b"
    r"|\bapellido\b"
    r"|\btel[eé]fono\b"
    r"|\bemail\b"
    r"|\bcorreo\b"
    r"|datos\s+de\s+contacto"
    r"|acepto\s+la\s+pol[ií]tica"
    r"|t[eé]rminos\s+y\s+condiciones"
    r"|solicitar\s+informaci[oó]n"
    r"|formulario",
    re.IGNORECASE,
)

FINANCIAL_RE = re.compile(
    r"\btrading\b"
    r"|\bforex\b"
    r"|\bfuturos\b"
    r"|\bopciones\b"
    r"|\bacciones\b"
    r"|\binvertir\b"
    r"|\binvierta\b"
    r"|\binversi[oó]n\b"
    r"|mercado\s+financiero"
    r"|ganar\s+dinero"
    r"|dinero\s+extra"
    r"|segundo\s+ingreso"
    r"|ingresos\s+ilimitados",
    re.IGNORECASE,
)

ROI_RE = re.compile(
    r"\+\s?\d{2,4}\s?%"
    r"|\b\d{2,4}\s?%\s*(?:de\s*)?(?:ganancia|rentabilidad|retorno|beneficio)"
    r"|\$\s?\d+(?:[.,]\d+)?\s*(?:a\s+la\s+semana|por\s+semana|por\s+d[ií]a)",
    re.IGNORECASE,
)

PAID_TRAFFIC_RE = re.compile(
    r"gad_source="
    r"|gclid="
    r"|gbraid="
    r"|utm_medium=cpc"
    r"|utm_source=google"
    r"|utm_source=taboola"
    r"|utm_medium=paid"
    r"|utm_campaign=",
    re.IGNORECASE,
)


def normalize_result(res):
    if res is None:
        return {
            "score": 0.0,
            "reasons": [],
            "evidence": [],
            "trust_bonus": 0.0,
        }

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
    return max(
        0.0,
        min(
            normalize_result(result)["score"],
            1.0,
        ),
    )


def _collect_signals(module_results: dict) -> list:
    signals = []
    seen = set()

    for module_name, result in module_results.items():
        n = normalize_result(result)

        if not n["reasons"] and n["score"] < 0.05:
            continue

        for reason in n["reasons"]:
            if reason in seen:
                continue

            seen.add(reason)

            signals.append({
                "label": SIGNAL_LABELS.get(
                    reason,
                    str(reason).replace("_", " ").capitalize(),
                ),
                "detail": n["evidence"][0] if n["evidence"] else "",
                "module": module_name,
            })

            if len(signals) >= 6:
                return signals

    return signals


_SCORE_ANCHORS = [
    (0.0, 0),
    (0.10, 22),
    (0.25, 50),
    (0.50, 75),
    (1.0, 100),
]


def _map_risk_to_score(risk: float) -> int:
    risk = max(0.0, min(risk, 1.0))

    for (x0, y0), (x1, y1) in zip(
        _SCORE_ANCHORS,
        _SCORE_ANCHORS[1:],
    ):
        if risk <= x1:
            return int(
                round(
                    y0 + (risk - x0) * (y1 - y0) / (x1 - x0)
                )
            )

    return 100


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower()
    except Exception:
        return ""


def _is_news_like(context: str, source_info: dict, url: str) -> bool:
    source_type = str(source_info.get("type", "")).lower()
    domain = _domain(url)

    return (
        context in NEWS_CONTEXTS
        or source_type in {"news", "news_media", "media"}
        or any(d in domain for d in NEWS_DOMAINS)
    )


def _is_institutional_like(context: str, source_info: dict) -> bool:
    source_type = str(source_info.get("type", "")).lower()

    return (
        context == "institutional"
        or source_type in INSTITUTIONAL_TYPES
    )


def _has_landing_intent(text: str, url: str, comm_data: dict) -> bool:
    t = text or ""
    u = url or ""

    form_hits = len(FORM_RE.findall(t))
    has_cta = bool(LANDING_CTA_RE.search(t))
    has_paid_traffic = bool(PAID_TRAFFIC_RE.search(u))

    commercial_signals = " ".join(
        str(signal)
        for signal in comm_data.get("signals", [])
    ).lower()

    comm_form_or_cta = (
        "formulario" in commercial_signals
        or "acción comercial" in commercial_signals
        or "captación" in commercial_signals
    )

    return (
        has_cta
        or form_hits >= 3
        or comm_form_or_cta
        or (has_paid_traffic and form_hits >= 2)
    )


def _has_financial_landing_intent(
    text: str,
    url: str,
    comm_data: dict,
) -> bool:
    financial = bool(
        FINANCIAL_RE.search(text or "")
        or FINANCIAL_RE.search(url or "")
        or ROI_RE.search(text or "")
    )

    return financial and _has_landing_intent(text, url, comm_data)


def _commercial_contribution(
    comm_data: dict,
    context: str,
    source_info: dict,
    text: str,
    url: str,
) -> float:
    raw_score = float(comm_data.get("score", 0) or 0)
    comm_risk = max(0.0, min(raw_score / 10.0, 1.0))

    if comm_risk <= 0:
        return 0.0

    news_like = _is_news_like(context, source_info, url)
    institutional_like = _is_institutional_like(context, source_info)
    landing_intent = _has_landing_intent(text, url, comm_data)
    financial_landing = _has_financial_landing_intent(text, url, comm_data)

    contribution = comm_risk * 0.35

    if institutional_like:
        return min(contribution, 0.04)

    if news_like and not landing_intent:
        return min(contribution, 0.05)

    if financial_landing:
        contribution = max(contribution, 0.24)

    return min(contribution, 0.35)


def _apply_risk_shields(
    risk_score: float,
    context: str,
    source_info: dict,
    url: str,
    text: str,
    comm_data: dict,
) -> float:
    news_like = _is_news_like(context, source_info, url)
    institutional_like = _is_institutional_like(context, source_info)
    landing_intent = _has_landing_intent(text, url, comm_data)

    if institutional_like:
        return min(risk_score, 0.18)

    if news_like and not landing_intent:
        # Evita falsos positivos tipo nota económica con "inversión".
        return min(risk_score, 0.42)

    return risk_score


def _apply_critical_floors(
    risk_score: float,
    text: str,
    url: str,
    comm_data: dict,
    promises_reasons: list,
    context: str,
    source_info: dict,
) -> float:
    news_like = _is_news_like(context, source_info, url)
    institutional_like = _is_institutional_like(context, source_info)

    if institutional_like:
        return risk_score

    financial_landing = _has_financial_landing_intent(text, url, comm_data)
    roi_detected = bool(ROI_RE.search(text or ""))

    has_promise = (
        "wealth_lure_pattern" in promises_reasons
        or "exaggerated_promises" in promises_reasons
    )

    if financial_landing and roi_detected:
        return max(risk_score, 0.62)

    if financial_landing and comm_data.get("level") == "alto":
        return max(risk_score, 0.60)

    if financial_landing and comm_data.get("level") == "medio":
        return max(risk_score, 0.38)

    if has_promise and financial_landing:
        return max(risk_score, 0.50)

    # Nunca aplicar piso comercial fuerte a una noticia sin landing.
    if news_like and not financial_landing:
        return risk_score

    if comm_data.get("level") == "alto" and not news_like:
        return max(risk_score, 0.52)

    return risk_score


def analyze_context(
    text: str,
    url: str = "",
    title: str = "",
    is_ecommerce: bool = False,
):
    try:
        if not text:
            return {
                "score": 0,
                "level": "bajo",
                "message": "Sin contenido para analizar",
                "signals": [],
                "confidence": 0,
                "engine_version": ENGINE_VERSION,
            }

        context = classify_context(text, url)

        if is_ecommerce and context == "general":
            context = "ecommerce"

        source_info = analyze_source(url, text)
        weights = adjust_weights(BASE_WEIGHTS, context, source_info)

        with ThreadPoolExecutor(max_workers=14) as executor:
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
                "uncertainty": executor.submit(
                    detect_uncertainty,
                    text,
                    title,
                    context,
                ),
                "structural": executor.submit(check_structural, text),
                "commercial_risk": executor.submit(
                    analyze_commercial_risk,
                    text,
                    url,
                    context,
                ),
            }

            results = {}

            for name, future in futures.items():
                try:
                    results[name] = future.result(timeout=2.0)
                except Exception:
                    traceback.print_exc()
                    results[name] = None

        scores = {
            key: _get_score(results[key])
            for key in BASE_WEIGHTS.keys()
        }

        structural_score = sum(
            scores[key] * weights.get(key, 0.1)
            for key in scores
        )

        comm_data = results["commercial_risk"] or {
            "score": 0,
            "level": "none",
            "summary": "",
            "signals": [],
        }

        commercial_score = _commercial_contribution(
            comm_data,
            context,
            source_info,
            text,
            url,
        )

        risk_score = structural_score + commercial_score

        authority_bonus = min(
            normalize_result(results["authority"])["trust_bonus"],
            0.15,
        )

        if source_info.get("type") == "institutional":
            risk_score = max(0.0, risk_score - 0.12)
            risk_score -= authority_bonus * 0.8

        elif context == "institutional":
            risk_score -= authority_bonus * 0.5

        else:
            risk_score -= authority_bonus * 0.25

        promises_reasons = normalize_result(
            results.get("promises")
        )["reasons"]

        risk_score = _apply_critical_floors(
            risk_score,
            text,
            url,
            comm_data,
            promises_reasons,
            context,
            source_info,
        )

        risk_score = _apply_risk_shields(
            risk_score,
            context,
            source_info,
            url,
            text,
            comm_data,
        )

        risk_score = max(0.0, min(risk_score, 1.0))

        final_score = _map_risk_to_score(risk_score)
        normalized_risk = final_score / 100

        MIN_CHARS_FOR_STRUCTURAL = 280
        clean_len = len((text or "").strip())

        if clean_len < MIN_CHARS_FOR_STRUCTURAL:
            alarm = max(
                scores.get("urgency", 0),
                scores.get("promises", 0),
                scores.get("narrative_patterns", 0),
                scores.get("emotions", 0),
            )

            commercial_alarm = comm_data.get("level") in ("medio", "alto")

            if alarm >= 0.4 or commercial_alarm:
                signals_short = _collect_signals({
                    key: results[key]
                    for key in results
                    if key != "commercial_risk"
                })

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
                        "El contenido es demasiado corto para un análisis "
                        "estructural completo, pero se detectaron señales de "
                        "presión o manipulación. Leé con cautela."
                    ),
                    "signals": signals_short[:6],
                    "confidence": None,
                    "context": context,
                    "source_type": source_info.get("type", "unknown"),
                    "commercial_risk": comm_data,
                    "engine_version": ENGINE_VERSION,
                    "pro": {},
                }

            return {
                "score": None,
                "level": "insuficiente",
                "message": "Texto insuficiente para análisis estructural",
                "insight": (
                    "El contenido es demasiado corto para evaluar de forma "
                    "confiable cómo está construido el mensaje. Chenuke se "
                    "abstiene en vez de dar un resultado injustificado."
                ),
                "signals": [],
                "confidence": None,
                "context": context,
                "source_type": source_info.get("type", "unknown"),
                "commercial_risk": comm_data,
                "engine_version": ENGINE_VERSION,
                "pro": {},
            }

        if normalized_risk >= 0.60:
            level = "alto"
            message = "Presión narrativa significativa detectada"

        elif normalized_risk >= 0.20:
            level = "medio"
            message = "Señales mixtas — lectura crítica recomendada"

        else:
            level = "bajo"
            message = "Bajo riesgo estructural detectado"

        module_results = {
            key: results[key]
            for key in results
            if key != "commercial_risk"
        }

        signals = _collect_signals(module_results)

        if comm_data.get("level") in ("medio", "alto"):
            signals.append({
                "label": "Riesgo comercial",
                "detail": comm_data.get("summary", ""),
                "module": "commercial_risk",
            })
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
            "pro": {
                "metrics": {
                    "emocionalidad": int(
                        max(
                            scores.get("emotions", 0),
                            scores.get("polarization", 0),
                        ) * 100
                    ),
                    "manipulacion": int(
                        max(
                            scores.get("urgency", 0),
                            scores.get("promises", 0),
                            scores.get("narrative_patterns", 0),
                        ) * 100
                    ),
                    "evidencia": int(
                        max(
                            0,
                            100 - scores.get("uncertainty", 0) * 100,
                        )
                    ),
                    "coherencia": int(
                        max(
                            0,
                            100 - scores.get("contradictions", 0) * 100,
                        )
                    ),
                }
            },
        }

    except Exception as e:
        traceback.print_exc()

        return {
            "score": 0,
            "level": "medio",
            "message": "Error en el motor",
            "signals": [{
                "label": "engine_error",
                "detail": str(e),
                "module": "engine",
            }],
            "confidence": 0,
            "engine_version": ENGINE_VERSION,
        }