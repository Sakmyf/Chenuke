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
    "investigación publicada", "peer.?review",
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

    # Respaldo fuerte: requiere calificador (no basta "estudio" solo)
    has_strong = any(ind in t for ind in _SUPPORT_INDICATORS)
    has_weak = any(ind in t for ind in _SUPPORT_WEAK)
    has_support = has_strong or (has_weak and has_strong)

    if not has_support:
        result.points += min(
            _SCORE_NO_SUPPORT_BASE + (len(matches) - 1) * _SCORE_NO_SUPPORT_PER_EXTRA,
            _SCORE_NO_SUPPORT_CAP,
        )
        result.reasons.append("unsupported_scientific_claim")
        result.evidence.append(
            f"Afirmación científica/salud sin respaldo ({len(matches)} señales)"
        )
    elif len(matches) >= _PARTIAL_SUPPORT_MIN_CLAIMS:
        result.points += _SCORE_PARTIAL_SUPPORT
        result.reasons.append("multiple_health_claims_with_partial_support")

    return result


def analyze(text: str) -> RuleResult:
    return check_scientific_claims(text)