"""promises — Detección de promesas exageradas o garantías absolutas.

Chenuke v15.21
Detecta:
- ganancias fáciles
- retornos exagerados
- ingresos ilimitados
- garantías absolutas
- bajo riesgo financiero prometido
- cambio de vida / transformación económica
"""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult


# ======================================================
# CONFIG
# ======================================================

_SIGNAL_NAME: Final[str] = "exaggerated_promises"

_SCORE_PER_HIT: float = 0.18
_MAX_SCORE: float = 1.0
_MAX_EVIDENCE: int = 6


# ======================================================
# PATRONES
# ======================================================

PROMISE_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        # Dinero / ingresos
        r"gan[aáe]?\s+dinero\s+(?:rápido|fácil|desde casa)",
        r"dinero\s+extra",
        r"segundo\s+ingreso",
        r"ingresos?\s+ilimitados?",
        r"gener[aáe]?\s+ingresos?",
        r"mejor[aáe]?\s+tus?\s+ganancias?",
        r"aprend[eé]\s+y\s+gan[aáe]",
        r"aprend[eé]\s+trading",

        # Facilidad exagerada
        r"sin\s+experiencia",
        r"sin\s+entrevista",
        r"tareas\s+sencillas",
        r"desde\s+casa",
        r"paso\s+a\s+paso",

        # Trading / inversión
        r"rentabilidad\s+asegurada",
        r"ganancias?\s+aseguradas?",
        r"sin\s+riesgo",
        r"riesgo\s+cero",
        r"domina[r]?\s+el\s+mercado",
        r"no\s+operes\s+solo",
        r"mercados?\s+reales",

        # Porcentajes / retornos
        r"\+\s?\d{2,4}\s?%",
        r"\b\d{2,4}\s?%\s*(?:de\s*)?(?:ganancia|rentabilidad|retorno|beneficio)",

        # Transformación emocional
        r"tu\s+vida\s+va\s+a\s+cambiar",
        r"libertad\s+financiera",
        r"viv[ií]\s+como\s+soñ[aá]s",
        r"cambi[aá]\s+tu\s+vida",
    )
]


def check_promises(text: str) -> RuleResult:
    result = RuleResult()
    t = text or ""

    hits: list[str] = []

    for pattern in PROMISE_RE:
        match = pattern.search(t)

        if match:
            hits.append(match.group(0))

    if hits:
        result.points += min(
            len(hits) * _SCORE_PER_HIT,
            _MAX_SCORE
        )

        result.reasons.append(_SIGNAL_NAME)
        result.evidence.extend(hits[:_MAX_EVIDENCE])

    return result


def analyze(text: str) -> RuleResult:
    return check_promises(text)