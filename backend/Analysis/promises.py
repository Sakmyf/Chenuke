"""promises — Promesas exageradas, garantías absolutas y señuelos de ganancia.

Chenuke v15.26

Dos familias de señal:
- exaggerated_promises: promesa de rendimiento, garantía absoluta,
  facilidad desproporcionada. Arquetipo: landing financiera / curso.
- wealth_lure_pattern: señuelo de dinero o premio sin contraprestación.
  Arquetipo: cadena de WhatsApp, sorteo falso, phishing de premio.

La segunda familia no existía y es la firma de la estafa viral más común
en LATAM.

El matcheo se hace sobre texto sin tildes; la evidencia sale del original.
"""

from __future__ import annotations

import re
from typing import Final

from backend.Analysis.rules_types import RuleResult
from backend.Analysis.text_norm import norm_for_match, evidence_from

_SIGNAL_PROMISE: Final[str] = "exaggerated_promises"
_SIGNAL_LURE: Final[str] = "wealth_lure_pattern"

_SCORE_PER_HIT: float = 0.18
_MAX_SCORE: float = 1.0
_MAX_EVIDENCE: int = 6


# ======================================================
# PROMESA DE RENDIMIENTO / GARANTÍA
# ======================================================

PROMISE_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        # Dinero / ingresos
        r"gan[aae]?\s+dinero\s+(?:rapido|facil|desde\s+casa)",
        r"dinero\s+extra",
        r"segundo\s+ingreso",
        r"ingresos?\s+ilimitados?",
        r"gener[aae]?\s+ingresos?",
        r"mejor[aae]?\s+tus?\s+ganancias?",
        r"aprend[ee]\s+y\s+gan[aae]",
        r"aprend[ee]\s+trading",

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

        # Transformación
        r"tu\s+vida\s+va\s+a\s+cambiar",
        r"libertad\s+financiera",
        r"vivi\s+como\s+soñas",
        r"cambi[aa]\s+tu\s+vida",

        # Estafas modernas
        r"(?:gana|ganar|obten)\s+(?:dinero|ingresos)\s+(?:sin\s+esfuerzo|facil|automaticamente)",
        r"(?:sistema|estrategia|metodo)\s+(?:probado|revolucionario|exclusivo)\s+(?:de\s+trading|de\s+inversion)",
        r"(?:curso|entrenamiento)\s+(?:gratuito|exclusivo)\s+(?:por\s+tiempo\s+limitado)",
        r"(?:oportunidad|inversion)\s+(?:unica|exclusiva)\s+(?:para\s+ti|solo\s+hoy)",
        r"(?:garantia|retorno)\s+(?:del\s+100\s?%|total|absoluto)",
        r"(?:sin\s+riesgo|riesgo\s+cero)\s+(?:de\s+perder|de\s+fracasar)",
        r"(?:multiplica|duplica|triplica)\s+tu\s+(?:dinero|inversion)",
        r"(?:sistema\s+automatico|bot)\s+(?:de\s+trading|de\s+inversion)",
    )
]


# ======================================================
# SEÑUELO DE DINERO / PREMIO
# Firma de cadena viral, sorteo falso y phishing de premio.
# ======================================================

LURE_RE: Final[list[re.Pattern]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        # Regalo / sorteo
        r"esta[n]?\s+regalando",
        r"\bregalando\b",
        r"te\s+(?:regalamos|regalan)",
        r"\bsorteo\b",
        r"sorte(?:amos|ando)",
        r"\bpremio\b",
        r"gran\s+premio",

        # Ganador / reclamo
        r"(?:ganaste|has\s+ganado|hs\s+ganado)",
        r"(?:sos|eres)\s+(?:el|la|un|una)\s+ganador",
        r"felicidades[,!\s]+(?:has|ganaste)",
        r"reclam[aa]?\s+tu\s+(?:premio|regalo|bono|cupon)",
        r"retir[aa]?\s+tu\s+(?:premio|dinero)",

        # Vales y cupones
        r"gift\s+card",
        r"tarjeta\s+de\s+regalo",
        r"cupon\s+de\s+\$?\s?[\d.,]+",
        r"bono\s+de\s+\$?\s?[\d.,]+",
        r"vale\s+de\s+compra",

        # Gratuidad absoluta
        r"(?:totalmente|completamente|100\s?%)\s+gratis",
        r"sin\s+costo\s+alguno",
        r"gratis\s+por\s+tiempo\s+limitado",

        # Monto regalado
        r"regalando\s+\$?\s?[\d.,]{3,}",
        r"\$\s?[\d.,]{3,}\s+(?:gratis|de\s+regalo|para\s+vos|para\s+ti)",

        # Prueba social de cobro
        r"(?:mis\s+amigos|un\s+amigo|mi\s+(?:primo|vecino|hermana?))\s+ya\s+(?:cobro|cobraron|recibio)",
        r"ya\s+(?:cobre|cobraron|lo\s+recibi|lo\s+recibieron)",
        r"a\s+mi\s+ya\s+me\s+(?:llego|pagaron)",

        # Cadena de reenvío (firma dura)
        r"(?:reenvia|reenviar|comparti|compartir|manda|mandar)\s+(?:este\s+)?mensaje",
        r"a\s+\d{1,3}\s+(?:grupos|contactos|amigos|personas)",
        r"compartilo\s+con\s+\d+",
        r"(?:solo\s+)?ten[eé]s\s+que\s+(?:compartir|reenviar)",
    )
]


def check_promises(text: str) -> RuleResult:
    result = RuleResult()
    original = text or ""
    t = norm_for_match(original)

    if not t:
        return result

    promise_hits: list[str] = []
    for pattern in PROMISE_RE:
        m = pattern.search(t)
        if m:
            promise_hits.append(evidence_from(original, m))

    lure_hits: list[str] = []
    for pattern in LURE_RE:
        m = pattern.search(t)
        if m:
            lure_hits.append(evidence_from(original, m))

    total_hits = len(promise_hits) + len(lure_hits)

    if not total_hits:
        return result

    result.points += min(
        total_hits * _SCORE_PER_HIT,
        _MAX_SCORE,
    )

    # El señuelo va primero: es la señal más específica y la que
    # dispara los pisos críticos del engine.
    if lure_hits:
        result.reasons.append(_SIGNAL_LURE)

    if promise_hits:
        result.reasons.append(_SIGNAL_PROMISE)

    result.evidence.extend((lure_hits + promise_hits)[:_MAX_EVIDENCE])

    return result


def analyze(text: str) -> RuleResult:
    return check_promises(text)