"""emotions — Detección de manipulación emocional.

Patrones que apuntan a activar una reacción emocional en el lector
(cambio de vida, libertad financiera, indignación, alarma).
"""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult

# FIX: signal name usa guion bajo para coincidir con SIGNAL_LABELS del engine.
# Antes: "manipulación emocional" (espacio) → no encontraba "manipulación_emocional" en el mapa.
_SIGNAL_NAME: Final[str] = "manipulación_emocional"

EMOTION_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE) for p in (
        r"cansado de", r"merecés", r"tu vida va a cambiar",
        r"libertad financiera", r"viví como soñás",
        r"impactante", r"alarmante", r"terrible",
        r"indignante", r"escandaloso",
    )
]

_PER_HIT: float = 0.10
_MAX_SCORE: float = 0.70
_MAX_EVIDENCE: int = 5


def analyze(text: str) -> RuleResult:
    result = RuleResult()
    t = text or ""
    hits = [m.group(0) for p in EMOTION_RE if (m := p.search(t))]
    if hits:
        result.points += min(_PER_HIT * len(hits), _MAX_SCORE)
        result.reasons.append(_SIGNAL_NAME)
        result.evidence.extend(hits[:_MAX_EVIDENCE])
    return result


def check_emotions(text: str) -> RuleResult:
    return analyze(text)