"""logical_fallacies — Detección de falacias lógicas comunes.

Chenuke v15.24
- Falso dilema (falsa dicotomía)
- Ad hominem (ataque a la persona)
- Generalización apresurada
"""

from __future__ import annotations

import re
from typing import Final
from backend.Analysis.rules_types import RuleResult

# ---------------------------------------------------------------------------
# Patrones de falacias
# ---------------------------------------------------------------------------

_FALSE_DILEMMA_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"o\s+(?:compras|haces|aceptas|te\s+sumas)\s+esto\s+o\s+(?:te\s+quedas|pierdes|fracasas)",
        r"solo\s+(?:dos|2)\s+opciones",
        r"si\s+no\s+(?:compras|inviertes|actúas)\s+ahora,\s+(?:perderás|te\sarrepentirás)",
        r"estás\s+(?:con\s+nosotros|en\s+contra)",
        r"o\s+estás\s+(?:conmigo|con\s+nosotros)\s+o\s+estás\s+(?:en\s+contra|contra\s+nosotros)",
    )
]

_AD_HOMINEM_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"los\s+que\s+critican\s+esto\s+no\s+entienden",
        r"los\s+escépticos\s+son\s+ignorantes",
        r"si\s+no\s+estás\s+de\s+acuerdo,\s+eres\s+(?:un\s+ignorante|un\s+negador|un\s+tonto)",
        r"los\s+que\s+dudan\s+son\s+(?:unos\s+ignorantes|unos\s+negacionistas)",
        r"los\s+que\s+critican\s+no\s+saben\s+de\s+lo\s+que\s+hablan",
    )
]

_HASTY_GENERALIZATION_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"todos\s+(?:los\s+que|los\s+inversores|los\s+expertos)\s+(?:ganan|saben|logran)",
        r"nadie\s+(?:puede|logra)\s+(?:ganar|tener\s+éxito)\s+sin\s+esto",
        r"siempre\s+(?:funciona|es\s+así|pasa)",
        r"todo\s+el\s+mundo\s+(?:lo\s+sabe|está\s+de\s+acuerdo)",
    )
]

# ---------------------------------------------------------------------------
# Umbrales
# ---------------------------------------------------------------------------

_SCORE_PER_FALLACY: float = 0.15
_MAX_SCORE: float = 0.45


def analyze(text: str) -> RuleResult:
    result = RuleResult()
    t = text or ""

    fallacies = []
    evidence_parts = []

    # Falso dilema
    for pattern in _FALSE_DILEMMA_RE:
        match = pattern.search(t)
        if match:
            fallacies.append("falso_dilema")
            evidence_parts.append(f"Falso dilema: '{match.group(0)}'")
            break

    # Ad hominem
    for pattern in _AD_HOMINEM_RE:
        match = pattern.search(t)
        if match:
            fallacies.append("ad_hominem")
            evidence_parts.append(f"Ataque ad hominem: '{match.group(0)}'")
            break

    # Generalización apresurada
    for pattern in _HASTY_GENERALIZATION_RE:
        match = pattern.search(t)
        if match:
            fallacies.append("generalización_apresurada")
            evidence_parts.append(f"Generalización apresurada: '{match.group(0)}'")
            break

    if fallacies:
        result.points = min(len(fallacies) * _SCORE_PER_FALLACY, _MAX_SCORE)
        result.reasons = fallacies
        result.evidence = evidence_parts

    return result