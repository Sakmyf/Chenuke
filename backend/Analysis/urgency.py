"""urgency — Detección de presión de urgencia artificial."""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult

# ---------------------------------------------------------------------------
# Patrones de urgencia estructural (precompilados)
# ---------------------------------------------------------------------------

# Frases completas: alta confianza de que es presión real.
_URGENCY_PHRASE_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"última oportunidad", r"actu[aá] ahora",
        r"antes (?:de )?que lo borren", r"solo\s+por\s+hoy",
        r"tiempo\s+limitado", r"decisión\s+inmediata",
    )
]

# FIX: "ahora", "ya", "oferta" como substrings libres generaban falsos
# positivos masivos. "Ya llegamos", "la oferta del super", "rápido y
# furioso" disparaban el módulo. Ahora se usan frases con contexto o
# word boundaries estrictos.
_URGENCY_TOKEN_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\burgente\b",
        r"\binmediat[oa]\b",
        r"\b(?:compra|oferta|promoción|descuento)\s+(?:ya|ahora|hoy)\b",
        r"\boportunidad\s+(?:única|última|limitada)\b",
        r"\bgan[eaá]\s+(?:ya|ahora|hoy)\b",
        r"\bno\s+(?:pierdas|pierde|pierdan)\b",
        r"\baprovech[aeá]\b",
    )
]

# ---------------------------------------------------------------------------
# Umbrales
# ---------------------------------------------------------------------------

_PHRASE_WEIGHT: int = 2       # las frases valen el doble que los tokens
_TOKEN_WEIGHT: int = 1
_SCORE_PER_UNIT: float = 0.15
_SCORE_CAP: float = 0.9


def check_urgency(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()

    phrase_hits = sum(1 for p in _URGENCY_PHRASE_RE if p.search(t))
    token_hits = sum(1 for p in _URGENCY_TOKEN_RE if p.search(t))

    total = phrase_hits * _PHRASE_WEIGHT + token_hits * _TOKEN_WEIGHT

    if total:
        result.points += min(total * _SCORE_PER_UNIT, _SCORE_CAP)
        result.reasons.append("urgency_pressure")
        result.evidence.append(f"Señales de urgencia detectadas: {total}")

    return result


def analyze(text: str) -> RuleResult:
    return check_urgency(text)