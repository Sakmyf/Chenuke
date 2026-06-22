"""polarization — Detección de lenguaje polarizante y generalizaciones."""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult

# ---------------------------------------------------------------------------
# Patrones (precompilados)
# ---------------------------------------------------------------------------

_POLARIZATION_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"ellos vs nosotros",
        r"la élite",
        r"el sistema",
        r"todos están en contra",
        r"los verdaderos culpables",
    )
]

# Generalizadores absolutos: muy frecuentes en español, por eso el
# umbral es alto (>3 ocurrencias) para evitar falsos positivos en
# textos largos donde "siempre" o "todos" aparecen de forma natural.
_GENERALIZATION_RE: Final[list[re.Pattern]] = [
    re.compile(p) for p in (r"\btodos\b", r"\bnadie\b", r"\bsiempre\b", r"\bnunca\b")
]

# ---------------------------------------------------------------------------
# Umbrales
# ---------------------------------------------------------------------------

_POLARIZATION_PER_HIT: float = 0.30
_POLARIZATION_CAP: float = 1.0
_GENERALIZATION_THRESHOLD: int = 3
_GENERALIZATION_SCORE: float = 0.30


def check_polarization(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    polarization_hits = 0

    for pattern in _POLARIZATION_RE:
        m = pattern.search(t)
        if m:
            polarization_hits += 1
            # FIX: mostrar el texto matcheado, no el regex crudo
            result.evidence.append(f"Patrón polarizante: {m.group(0)!r}")

    generalizations = sum(len(p.findall(t)) for p in _GENERALIZATION_RE)

    if polarization_hits:
        result.points += min(polarization_hits * _POLARIZATION_PER_HIT, _POLARIZATION_CAP)
        result.reasons.append("polarization_detected")

    if generalizations > _GENERALIZATION_THRESHOLD:
        result.points += _GENERALIZATION_SCORE
        result.reasons.append("overgeneralization")

    return result


def analyze(text: str) -> RuleResult:
    return check_polarization(text)