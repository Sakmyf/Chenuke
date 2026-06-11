"""
detect_uncertainty v3.0 — Incertidumbre informativa con abstención estructural.

Principio (ETHICS.md): "la abstención responsable es preferible a una
clasificación injustificada".

Cambio v3.0: el módulo solo evalúa cuando el texto contiene AFIRMACIONES
VERIFICABLES (números, categóricos, condicionales, hechos recientes).
Una portada institucional, una landing o una página navegacional sin claims
no tiene "incertidumbre" que medir: exigirle fuentes a una home es un error
de categoría que generaba falsos positivos (ej.: vatican.va marcado moderado).

Esto es estructural y agnóstico de idioma/país/dominio: no depende de listas
de instituciones (imposibles de mantener para LATAM + España + resto del
mundo). El motor no juzga QUIÉN habla, sino si lo dicho REQUIERE evidencia.

La detección de manipulación (urgencia, emociones, promesas, etc.) NO pasa
por este módulo y sigue activa siempre: una landing corta que grita "GANÁ YA"
se detecta igual por los otros módulos.
"""

import re
from backend.Analysis.rules_types import RuleResult

NUMBER_PATTERNS = [r"\b\d+[\.,]?\d*\s*(mil|millones?|billones?|personas?|empleos?|puestos?|casos?|muertes?|contagios?)\b", r"\b\d+\s*%", r"\b\d+\s*de\s*cada\s*\d+\b"]
STRONG_SOURCES = [r"\bindec\b", r"\bcepal\b", r"\boms\b", r"\bministerio\b", r"\bgobierno\b", r"\boficial\b", r"\bestadística\b"]
WEAK_SOURCES = [r"\bestudio\b", r"\binforme\b", r"\bdatos\b", r"\bsegún\b", r"\bfuentes\b"]
CONDITIONAL_PATTERNS = [r"\bhabría\b", r"\bhabrían\b", r"\bsería\b", r"\bserían\b", r"\bestaría\b", r"\bestarían\b", r"\bpodría\b", r"\bpodrían\b", r"\btrascendió\b", r"\bse especula\b"]
CATEGORICAL_UNVERIFIED = [r"\bes el peor\b", r"\bes el mejor\b", r"\bnunca antes\b", r"\bjamás\b", r"\bhistórico\b", r"\bsin precedentes\b", r"\bla mayor\b", r"\bla menor\b", r"\bcompletamente\b", r"\btotalmente\b"]
RECENCY_PATTERNS = [r"\bhoy\b", r"\bayer\b", r"\banoche\b", r"\besta\s+mañana\b", r"\bhoras\s+atrás\b", r"\bminutos\s+atrás\b"]

# Umbrales estructurales (caracteres). Deterministas y documentados.
MIN_BODY_FOR_ANALYSIS = 600   # debajo de esto y sin claims → abstención total
MIN_BODY_FOR_TITLE_GAP = 400  # un "gap titular/cuerpo" requiere que exista un cuerpo


def _length_factor(n: int, claim_density: int) -> float:
    """Atenuación por longitud, MODULADA por densidad de señales.

    Un texto corto AMBIGUO (pocas señales) se atenúa: poca evidencia para
    penalizar con certeza. Pero un texto corto CARGADO de claims (condicionales,
    categóricos, números acumulados) NO se atenúa: es breve pero inequívocamente
    manipulador (típico de un posteo viral o un copy de estafa).
    """
    if claim_density >= 3:
        return 1.0
    if n >= 1000:
        return 1.0
    if n >= 600:
        return 0.85
    return 0.65


def detect_uncertainty(text: str, title: str = "", context: str = "general") -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    title_lower = (title or "").lower()

    if context in ["ecommerce", "product", "landing"]:
        return result

    # Multiplier por contexto. Institucional atenúa (organismos rara vez
    # desinforman estructuralmente); social va PLENO porque las redes
    # concentran contenido viral no verificado.
    if context in ["government", "institutional"]:
        multiplier = 0.3
    elif context in ["news", "news_media", "social"]:
        multiplier = 1.0
    else:
        multiplier = 0.6

    # --- Detección de afirmaciones verificables (claims) ---
    has_strong = any(re.search(p, t) for p in STRONG_SOURCES)
    has_weak = any(re.search(p, t) for p in WEAK_SOURCES)
    has_numbers = any(re.search(p, t) for p in NUMBER_PATTERNS)
    categorical = [p for p in CATEGORICAL_UNVERIFIED if re.search(p, t)]
    conditional_count = sum(len(re.findall(p, t)) for p in CONDITIONAL_PATTERNS)
    recency = [p for p in RECENCY_PATTERNS if re.search(p, t)]

    has_verifiable_claims = bool(has_numbers or categorical or recency or conditional_count > 0)

    # --- Abstención estructural ---
    # Texto corto SIN afirmaciones verificables = portada/landing/navegación.
    # No hay nada que verificar → no se inventa riesgo. (Funciona para
    # cualquier institución del mundo sin listas de dominios.)
    if len(t) < MIN_BODY_FOR_ANALYSIS and not has_verifiable_claims:
        return result

    # Texto breve pero con claims: se evalúa, atenuado según densidad de señales.
    claim_density = (len(categorical) + (1 if has_numbers else 0) +
                     (1 if recency else 0) + min(conditional_count, 3))
    length_factor = _length_factor(len(t), claim_density)

    score = 0.0
    if has_numbers and not has_strong:
        score += 0.10 if has_weak else 0.25
        result.reasons.append("numbers_without_strong_source")
        result.evidence.append("Datos numéricos sin fuente sólida")

    allowed = int(max(1.0, len(text or "") / 1000.0) * 3)
    if conditional_count > allowed:
        score += min(0.3, (conditional_count - allowed) * 0.05)
        result.reasons.append("excessive_conditional_language")
        result.evidence.append(f"Uso excesivo de condicionales ({conditional_count}, esperado max {allowed})")

    if categorical and not has_strong:
        score += 0.20
        result.reasons.append("unverified_categorical_claim")
        result.evidence.append("Afirmación categórica sin respaldo")

    if recency and (categorical or has_numbers) and not has_strong:
        score += 0.15
        result.reasons.append("recent_unattributed_claim")
        result.evidence.append("Hecho reciente sin atribución clara")

    # Gap titular/cuerpo: solo tiene sentido si EXISTE un cuerpo que pueda
    # (o no) respaldar al titular. Una home de titular grande no es un "gap".
    if title_lower and len(t) >= MIN_BODY_FOR_TITLE_GAP:
        title_strong = any(re.search(p, title_lower) for p in CATEGORICAL_UNVERIFIED + NUMBER_PATTERNS)
        body_supports = has_strong or sum(1 for p in WEAK_SOURCES if re.search(p, t)) >= 2
        if title_strong and not body_supports:
            score += 0.20
            result.reasons.append("title_body_gap")
            result.evidence.append("El titular no está respaldado por el contenido")

    result.points = round(min(score * multiplier * length_factor, 0.45), 3)
    result.reasons = list(dict.fromkeys(result.reasons))
    result.evidence = list(dict.fromkeys(result.evidence))
    return result


def analyze(text: str, title: str = "", context: str = "general"):
    return detect_uncertainty(text, title, context)
