"""misinformation — Detección de acusaciones graves, lenguaje conspirativo y
afirmaciones categóricas sin respaldo.

Principio: una acusación de fraude/corrupción sin atribución concreta es
la señal más fuerte de desinformación. Pero el check de atribución debe ser
ESTRICTO (no basta una mención casual de "según" en cualquier parte).
"""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult

# ---------------------------------------------------------------------------
# Patrones (precompilados)
# ---------------------------------------------------------------------------

_SERIOUS_CLAIM_RE: Final[list[re.Pattern]] = [
    re.compile(p) for p in (r"\bfraude\b", r"\bestafa\b", r"\bcorrupción\b", r"\bengaño\b", r"\bilegal\b")
]

_CONSPIRACY_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"no quieren que sepas", r"te están ocultando",
        r"nadie habla de", r"verdad oculta",
    )
]

_CATEGORICAL_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"es un hecho", r"está probado", r"sin dudas", r"queda demostrado",
    )
]

# FIX: atribución ESTRICTA. Antes "según" y "dijo" bastaban para desactivar
# la detección de acusación grave — palabras demasiado comunes que un scam
# incluye casualmente. Ahora se exige una atribución CONCRETA (verbo de
# declaración + nombre/cita), no una mención genérica.
#
# Patrón: "según [nombre]", "informó [nombre]", "declaró que", etc.
_STRICT_ATTRIBUTION_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\bsegún\s+\w{3,}",           # "según el ministro" (no solo "según")
        r"\b(?:informó|declaró|afirmó|aseguró|confirmó)\s+(?:que\s+)?(?:el|la|los|las)\s+\w{3,}",
        r"\bde acuerdo con\s+\w{3,}",
        r"\b(?:informe|reporte)\s+(?:de|del)\s+\w{3,}",
    )
]

# ---------------------------------------------------------------------------
# Umbrales
# ---------------------------------------------------------------------------

SCORE_SERIOUS_NO_SOURCE: float = 0.9
SCORE_CONSPIRACY: float = 0.8
SCORE_CATEGORICAL: float = 0.6


def check_misinformation(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()

    # 1) Acusación grave sin atribución estricta
    serious_found = [p.pattern for p in _SERIOUS_CLAIM_RE if p.search(t)]
    has_strict_attribution = any(p.search(t) for p in _STRICT_ATTRIBUTION_RE)

    if serious_found and not has_strict_attribution:
        result.points += SCORE_SERIOUS_NO_SOURCE
        result.reasons.append("serious_accusation_without_source")
        result.evidence.append(f"Acusación grave sin fuente: {', '.join(serious_found)}")

    # 2) Lenguaje conspirativo
    if any(p.search(t) for p in _CONSPIRACY_RE):
        result.points += SCORE_CONSPIRACY
        result.reasons.append("conspiracy_language")
        result.evidence.append("Lenguaje conspirativo detectado")

    # 3) Afirmaciones categóricas
    if any(p.search(t) for p in _CATEGORICAL_RE):
        result.points += SCORE_CATEGORICAL
        result.reasons.append("categorical_claim")
        result.evidence.append("Afirmación categórica fuerte")

    return result


def analyze(text: str) -> RuleResult:
    return check_misinformation(text)