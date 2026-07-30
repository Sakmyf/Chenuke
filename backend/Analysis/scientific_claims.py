"""scientific_claims — Afirmaciones de salud/ciencia sin respaldo."""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult

# ---------------------------------------------------------------------------
# Patrones de reclamos de salud/ciencia (precompilados)
# ---------------------------------------------------------------------------

_MEDICAL_CLAIM_RE: Final[list[re.Pattern]] = [
    re.compile(p) for p in (
        r"\bcurar\b",                          # verbo específico (no "cura" sustantivo)
        r"tratamiento definitivo", r"100 ?% efectivo",
        r"comprobado científicamente", r"reemplaza la medicina",
        r"la medicina no quiere que sepas",
        r"avalado por médicos", r"científicamente probado",
        r"sin efectos secundarios", r"cura definitiva",
        r"\bcure[sd]?\b", r"100 ?% effective",
        r"scientifically (?:proven|backed|validated)",
        r"science.?backed", r"clinically proven",
        r"doctors (?:don.?t want|hate)",
        r"(?:extend|reverse|stop) aging",
        r"miracle (?:cure|solution|treatment)",
    )
]

# FIX: indicadores de respaldo más estrictos. "estudio" solo es demasiado
# loose — "un estudio de mercado", "estudio de caso" no son respaldo
# científico. Se exige al menos un calificador ("clínico", "publicado",
# "universidad") o una fuente reconocida.
_SUPPORT_INDICATORS: Final[tuple[str, ...]] = (
    "ensayo clínico", "universidad", "revista científica",
    "publicado en", "journal of", "clinical trial",
    "published in", "nih", "who", "lancet", "nature",
    "investigación publicada",
    # FIX v15.25: eran sintaxis regex en un check de substring → nunca matcheaban
    "peer review", "peer-review", "revisión por pares",
)

# Indicadores débiles: contribuyen pero no bastan por sí solos.
_SUPPORT_WEAK: Final[tuple[str, ...]] = (
    "estudio", "investigación", "according to", "research",
)

# ---------------------------------------------------------------------------
# Umbrales
# ---------------------------------------------------------------------------

_SCORE_NO_SUPPORT_BASE: float = 0.7
_SCORE_NO_SUPPORT_PER_EXTRA: float = 0.1
_SCORE_NO_SUPPORT_CAP: float = 1.0
_SCORE_PARTIAL_SUPPORT: float = 0.2
_PARTIAL_SUPPORT_MIN_CLAIMS: int = 3


def check_scientific_claims(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()

    matches = [p.pattern for p in _MEDICAL_CLAIM_RE if p.search(t)]
    if not matches:
        return result

    # FIX v15.25: la expresión anterior `has_strong or (has_weak and has_strong)`
    # era código muerto — has_weak nunca aportaba. Semántica correcta:
    # solo el respaldo FUERTE anula la penalización; el débil ("estudio",
    # "según") atenúa pero no anula (ver rama elif más abajo).
    has_strong = any(ind in t for ind in _SUPPORT_INDICATORS)
    has_weak = any(ind in t for ind in _SUPPORT_WEAK)

    if not has_strong and not has_weak:
        result.points += min(
            _SCORE_NO_SUPPORT_BASE + (len(matches) - 1) * _SCORE_NO_SUPPORT_PER_EXTRA,
            _SCORE_NO_SUPPORT_CAP,
        )
        result.reasons.append("unsupported_scientific_claim")
        result.evidence.append(
            f"Afirmación científica/salud sin respaldo ({len(matches)} señales)"
        )
    elif not has_strong:
        # Solo respaldo débil ("estudio", "según"): penalización reducida
        result.points += _SCORE_PARTIAL_SUPPORT
        result.reasons.append("weak_support_for_health_claims")
        result.evidence.append("Reclamo de salud con respaldo débil o genérico")
    elif len(matches) >= _PARTIAL_SUPPORT_MIN_CLAIMS:
        result.points += _SCORE_PARTIAL_SUPPORT
        result.reasons.append("multiple_health_claims_with_partial_support")

    return result


def analyze(text: str) -> RuleResult:
    return check_scientific_claims(text)