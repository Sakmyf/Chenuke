"""
detect_uncertainty v3.1 — Incertidumbre informativa con abstención estructural.

Principio (ETHICS.md): "la abstención responsable es preferible a una
clasificación injustificada".

El módulo solo evalúa cuando el texto contiene AFIRMACIONES VERIFICABLES
(números, categóricos, condicionales, hechos recientes). Una portada
institucional o landing sin claims no tiene "incertidumbre" que medir.

La detección de manipulación (urgencia, emociones, promesas) NO pasa por
este módulo y sigue activa siempre.

v3.1: regex precompilados, context check corregido, constantes nombradas.
"""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult

# ---------------------------------------------------------------------------
# Patrones regex — precompilados una sola vez
# ---------------------------------------------------------------------------

_NUMBER_RE: Final[list[re.Pattern]] = [
    re.compile(p)
    for p in (
        r"\b\d+[\.,]?\d*\s*(?:mil|millones?|billones?|personas?|empleos?|puestos?|casos?|muertes?|contagios?)\b",
        r"\b\d+\s*%",
        r"\b\d+\s+de\s+cada\s+\d+\b",
    )
]

_STRONG_SOURCE_RE: Final[list[re.Pattern]] = [
    re.compile(p) for p in (
        r"\bindec\b", r"\bcepal\b", r"\boms\b", r"\bministerio\b",
        r"\bestadísticas?\b", r"\binstituto\b", r"\buniversidad\b",
    )
]

_WEAK_SOURCE_RE: Final[list[re.Pattern]] = [
    re.compile(p) for p in (
        r"\bestudio\b", r"\binforme\b", r"\bdatos\b", r"\bsegún\b",
        r"\bfuentes?\b", r"\breporte\b",
    )
]

_ATTRIBUTION_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\b(?:informó|informaron|sostuvo|sostuvieron|declaró|declararon|afirmó|afirmaron)\b",
        r"\b(?:aseguró|aseguraron|indicó|indicaron|reveló|revelaron|confirmó|confirmaron)\b",
        r"\b(?:anunció|anunciaron|explicó|explicaron|señaló|señalaron|precisó|detalló)\b",
        r"\b(?:according to|de acuerdo (?:a|con)|tal como|conforme a)\b",
        r"\bsegún\s+(?!se\s+especula|trascendió|rumor|dicen|comentan|se\s+rumorea)\w+",
        r"[«\"\u201c][^»\"\u201d]{10,}[»\"\u201d]",
        r"\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b",
    )
]

_CONDITIONAL_RE: Final[list[re.Pattern]] = [
    re.compile(p) for p in (
        r"\bhabría\b", r"\bhabrían\b", r"\bsería\b", r"\bserían\b",
        r"\bestaría\b", r"\bestarían\b", r"\bpodría\b", r"\bpodrían\b",
        r"\btrascendió\b", r"\bse especula\b",
    )
]

_CATEGORICAL_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\bes el peor\b", r"\bes el mejor\b", r"\bnunca antes\b",
        r"\bjamás\b", r"\bhistórico\b", r"\bsin precedentes\b",
        r"\bla mayor\b", r"\bla menor\b", r"\bcompletamente\b", r"\btotalmente\b",
    )
]

_RECENCY_RE: Final[list[re.Pattern]] = [
    re.compile(p) for p in (
        r"\bhoy\b", r"\bayer\b", r"\banoche\b",
        r"\besta\s+mañana\b", r"\bhoras\s+atrás\b", r"\bminutos\s+atrás\b",
    )
]

# ---------------------------------------------------------------------------
# Umbrales estructurales
# ---------------------------------------------------------------------------

MIN_BODY_FOR_ANALYSIS: int = 600
MIN_BODY_FOR_TITLE_GAP: int = 400
CONDITIONALS_PER_1000_CHARS: int = 3
MAX_SCORE: float = 0.45

# Context multipliers
MULTIPLIER_INSTITUTIONAL: float = 0.3
MULTIPLIER_NEWS_SOCIAL: float = 1.0
MULTIPLIER_DEFAULT: float = 0.6

# Score por señal
SCORE_NUMBERS_NO_SOURCE: float = 0.25
SCORE_NUMBERS_WEAK_SOURCE: float = 0.10
SCORE_CONDITIONAL_EXCESS_PER_UNIT: float = 0.05
SCORE_CONDITIONAL_CAP: float = 0.30
SCORE_CATEGORICAL: float = 0.20
SCORE_RECENT_UNATTRIBUTED: float = 0.15
SCORE_TITLE_BODY_GAP: float = 0.20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _any_match(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def _match_list(patterns: list[re.Pattern], text: str) -> list[str]:
    return [p.pattern for p in patterns if p.search(text)]


def _count_matches(patterns: list[re.Pattern], text: str) -> int:
    return sum(len(p.findall(text)) for p in patterns)


def _length_factor(n: int, claim_density: int) -> float:
    """Atenuación por longitud, modulada por densidad de señales."""
    if claim_density >= 3:
        return 1.0
    if n >= 1000:
        return 1.0
    if n >= 600:
        return 0.85
    return 0.65


def allowed_conditionals(text: str) -> int:
    """Condicionales tolerados según longitud (3 cada 1000 chars)."""
    return int(max(1.0, len(text or "") / 1000.0) * CONDITIONALS_PER_1000_CHARS)


# ---------------------------------------------------------------------------
# Análisis principal
# ---------------------------------------------------------------------------

# Contextos donde el módulo se abstiene por completo
_SKIP_CONTEXTS: frozenset[str] = frozenset({"ecommerce", "product", "landing"})
# Contextos con multiplicador alto (contenido viral no verificado)
_HIGH_MULTIPLIER_CONTEXTS: frozenset[str] = frozenset({"news", "news_media", "social"})


def detect_uncertainty(
    text: str, title: str = "", context: str = "general"
) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    title_lower = (title or "").lower()

    if context in _SKIP_CONTEXTS:
        return result

    # FIX v3.1: "government" nunca lo devuelve classify_context. Solo "institutional".
    if context == "institutional":
        multiplier = MULTIPLIER_INSTITUTIONAL
    elif context in _HIGH_MULTIPLIER_CONTEXTS:
        multiplier = MULTIPLIER_NEWS_SOCIAL
    else:
        multiplier = MULTIPLIER_DEFAULT

    # --- Detección de afirmaciones verificables ---
    has_strong = _any_match(_STRONG_SOURCE_RE, t)
    has_weak = _any_match(_WEAK_SOURCE_RE, t)
    has_numbers = _any_match(_NUMBER_RE, t)
    categorical = _match_list(_CATEGORICAL_RE, t)
    conditional_count = _count_matches(_CONDITIONAL_RE, t)
    recency = _match_list(_RECENCY_RE, t)

    # Atribución estructural
    attribution_hits = sum(1 for p in _ATTRIBUTION_RE if p.search(t))

    # Anti-falsificación: atribución no blinda si hay banderas rojas
    fake_load = len(categorical) + (1 if conditional_count > allowed_conditionals(text) else 0)
    has_attribution = attribution_hits >= 2 and fake_load < 2
    is_supported = has_strong or has_attribution

    has_verifiable_claims = bool(has_numbers or categorical or recency or conditional_count > 0)

    # --- Abstención estructural ---
    if len(t) < MIN_BODY_FOR_ANALYSIS and not has_verifiable_claims:
        return result

    # Densidad de señales para atenuación por longitud
    claim_density = (
        len(categorical)
        + (1 if has_numbers else 0)
        + (1 if recency else 0)
        + min(conditional_count, 3)
    )
    length_factor = _length_factor(len(t), claim_density)

    # --- Scoring ---
    score = 0.0

    if has_numbers and not is_supported:
        score += SCORE_NUMBERS_WEAK_SOURCE if has_weak else SCORE_NUMBERS_NO_SOURCE
        result.reasons.append("numbers_without_strong_source")
        result.evidence.append("Datos numéricos sin fuente sólida")

    allowed = allowed_conditionals(text)
    if conditional_count > allowed:
        score += min(
            SCORE_CONDITIONAL_EXCESS_PER_UNIT * (conditional_count - allowed),
            SCORE_CONDITIONAL_CAP,
        )
        result.reasons.append("excessive_conditional_language")
        result.evidence.append(
            f"Uso excesivo de condicionales ({conditional_count}, esperado max {allowed})"
        )

    if categorical and not is_supported:
        score += SCORE_CATEGORICAL
        result.reasons.append("unverified_categorical_claim")
        result.evidence.append("Afirmación categórica sin respaldo")

    if recency and (categorical or has_numbers) and not is_supported:
        score += SCORE_RECENT_UNATTRIBUTED
        result.reasons.append("recent_unattributed_claim")
        result.evidence.append("Hecho reciente sin atribución clara")

    # Gap titular/cuerpo
    if title_lower and len(t) >= MIN_BODY_FOR_TITLE_GAP:
        title_strong = _any_match(_CATEGORICAL_RE + _NUMBER_RE, title_lower)
        body_supports = is_supported or sum(1 for p in _WEAK_SOURCE_RE if p.search(t)) >= 2
        if title_strong and not body_supports:
            score += SCORE_TITLE_BODY_GAP
            result.reasons.append("title_body_gap")
            result.evidence.append("El titular no está respaldado por el contenido")

    result.points = round(min(score * multiplier * length_factor, MAX_SCORE), 3)
    result.reasons = list(dict.fromkeys(result.reasons))
    result.evidence = list(dict.fromkeys(result.evidence))
    return result


def analyze(text: str, title: str = "", context: str = "general") -> RuleResult:
    return detect_uncertainty(text, title, context)