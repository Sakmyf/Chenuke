"""structural — Generalizaciones absolutas, clickbait y uso excesivo de mayúsculas."""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult

# ---------------------------------------------------------------------------
# Patrones (precompilados)
# ---------------------------------------------------------------------------

_ABSOLUTE_RE: Final[list[re.Pattern]] = [
    re.compile(p) for p in (r"\btodos\b", r"\bnadie\b", r"\bsiempre\b", r"\bnunca\b")
]

_CLICKBAIT_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"no vas a creer", r"lo que pasó después", r"te sorprenderá",
        r"impactante", r"increíble",
    )
]

# ---------------------------------------------------------------------------
# Umbrales
# ---------------------------------------------------------------------------

_ABSOLUTES_PER_1000_CHARS: int = 4
_ABSOLUTE_PER_EXCESS: float = 0.10
_ABSOLUTE_CAP: float = 0.80
_CLICKBAIT_PER_HIT: float = 0.20
_CLICKBAIT_CAP: float = 0.70
_UPPERCASE_THRESHOLD: float = 0.25
_UPPERCASE_MIN_LENGTH: int = 30
_UPPERCASE_SCORE: float = 0.60

# NOTA: estos absolutos (todos, nadie, siempre, nunca) también los checkea
# `polarization.py` como `GENERALIZATION_PATTERNS`. Es intencional: miden
# cosas distintas — aquí es generalización desproporcionada (estructura),
# allí es lenguaje polarizante (división). El motor los pondera por separado
# y la renormalización de pesos evita doble conteo excesivo.


def check_structural(text: str) -> RuleResult:
    result = RuleResult()
    raw = text or ""
    t = raw.lower()
    text_length = len(raw)

    # --- Generalizaciones absolutas (tolerancia por longitud) ---
    text_length_k = max(1.0, text_length / 1000.0)
    allowed = int(text_length_k * _ABSOLUTES_PER_1000_CHARS)

    absolute_count = sum(len(p.findall(t)) for p in _ABSOLUTE_RE)
    if absolute_count > allowed:
        excess = absolute_count - allowed
        result.points += min(excess * _ABSOLUTE_PER_EXCESS, _ABSOLUTE_CAP)
        result.reasons.append("absolute_generalization")
        result.evidence.append(
            f"Uso desproporcionado de generalizaciones "
            f"({absolute_count}, esperado max {allowed})"
        )

    # --- Patrones clickbait ---
    clickbait = [m.group(0) for p in _CLICKBAIT_RE if (m := p.search(t))]
    if clickbait:
        result.points += min(len(clickbait) * _CLICKBAIT_PER_HIT, _CLICKBAIT_CAP)
        result.reasons.append("clickbait_structure")
        result.evidence.append(
            f"Patrones clickbait detectados: {', '.join(clickbait)}"
        )

    # --- Uso excesivo de mayúsculas ---
    if text_length > _UPPERCASE_MIN_LENGTH:
        uppercase_count = sum(1 for c in raw if c.isupper())
        uppercase_ratio = uppercase_count / text_length
        if uppercase_ratio > _UPPERCASE_THRESHOLD:
            result.points += _UPPERCASE_SCORE
            result.reasons.append("excessive_uppercase")
            result.evidence.append(
                f"Uso excesivo de mayúsculas ({int(uppercase_ratio * 100)}%)"
            )

    return result


def analyze(text: str) -> RuleResult:
    return check_structural(text)