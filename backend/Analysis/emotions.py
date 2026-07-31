"""emotions — Detección de manipulación emocional.

Chenuke v15.26

Dos niveles de confianza:

- ALTA: marcadores de presión emocional directa sobre el lector
  (imperativos de acción inmediata, afirmación de verdad sin fuente,
  ganchos de incredulidad). Son específicos del discurso manipulador.

- BAJA: vocabulario de alarma. Aparece también en periodismo legítimo y
  en advertencias policiales, así que pondera mucho menos y el
  weight_engine lo atenúa en contextos de noticia.

El matcheo se hace sobre texto sin tildes (ver text_norm); la evidencia
se extrae del texto ORIGINAL para que la cita sea fiel.
"""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult
from backend.Analysis.text_norm import norm_for_match, evidence_from

# El nombre lleva tilde a propósito: es la clave del mapa SIGNAL_LABELS
# en engine.py. NO cambiar sin actualizar ese dict.
_SIGNAL_NAME: Final[str] = "manipulación_emocional"


# ======================================================
# ALTA CONFIANZA — presión directa sobre el lector
# ======================================================

STRONG_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        # Imperativos de acción inmediata
        r"no\s+lo\s+dudes",
        r"no\s+dudes\s+en",
        r"no\s+te\s+lo\s+pierdas",
        r"(?:hacelo|hazlo|haganlo)\s+(?:ya|ahora)",
        r"(?:actua|actuen|actua)\s+(?:ya|ahora|rapido)",
        r"apur(?:ate|ense|a)\b",
        r"corre\s+a\s+(?:comprar|reclamar|anotarte)",

        # Afirmación de verdad sin fuente
        r"es\s+(?:completamente|totalmente|100\s?%)\s+(?:real|verdad|cierto)",
        r"(?:te\s+lo\s+juro|juro\s+que\s+es)",
        r"(?:yo\s+)?ya\s+lo\s+(?:probe|comprobe|verifique)",
        r"funciona\s+de\s+verdad",
        r"a\s+mi\s+me\s+funciono",

        # Ganchos de incredulidad / clickbait emocional
        r"no\s+(?:te\s+)?(?:lo\s+)?vas\s+a\s+creer",
        r"(?:mira|miren|vean)\s+(?:esto|lo\s+que)",
        r"te\s+va\s+a\s+sorprender",
        r"nadie\s+te\s+lo\s+(?:va\s+a\s+)?(?:decir|cuenta)",

        # Transformación / deseo (patrones originales v15.24)
        r"tu\s+vida\s+va\s+a\s+cambiar",
        r"libertad\s+financiera",
        r"vivi\s+como\s+soñas",
        r"cansado\s+de",
        r"mereces\b",
        r"te\s+lo\s+mereces",
    )
]


# ======================================================
# BAJA CONFIANZA — vocabulario de alarma
# Riesgo de falso positivo en noticias y advertencias legítimas:
# una nota policial sobre una estafa usa este mismo vocabulario
# para denunciarla. Por eso pesa poco.
# ======================================================

WEAK_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\batencion\b",
        r"\burgente\b",
        r"\balerta\b",
        r"\bcuidado\b",
        r"impactante",
        r"alarmante",
        r"terrible",
        r"indignante",
        r"escandaloso",
        r"increible",
        r"impresionante",
        r"verguenza",
        r"basta\s+de",
        r"no\s+puede\s+ser",
    )
]


_PER_STRONG: float = 0.14
_PER_WEAK: float = 0.05
_MAX_SCORE: float = 0.85
_MAX_EVIDENCE: int = 5


def analyze(text: str) -> RuleResult:
    result = RuleResult()
    original = text or ""
    t = norm_for_match(original)

    if not t:
        return result

    strong_hits: list[str] = []
    for pattern in STRONG_RE:
        m = pattern.search(t)
        if m:
            strong_hits.append(evidence_from(original, m))

    weak_hits: list[str] = []
    for pattern in WEAK_RE:
        m = pattern.search(t)
        if m:
            weak_hits.append(evidence_from(original, m))

    if not strong_hits and not weak_hits:
        return result

    score = (
        _PER_STRONG * len(strong_hits)
        + _PER_WEAK * len(weak_hits)
    )

    result.points += min(score, _MAX_SCORE)
    result.reasons.append(_SIGNAL_NAME)

    # La evidencia fuerte va primero: engine.py muestra evidence[0]
    # como cita del hallazgo en el listado de señales.
    result.evidence.extend((strong_hits + weak_hits)[:_MAX_EVIDENCE])

    return result


def check_emotions(text: str) -> RuleResult:
    return analyze(text)