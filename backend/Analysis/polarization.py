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
        # Contraposición explícita nosotros/ellos.
        r"ellos\s+(?:vs\.?|versus|contra|o)\s+nosotros",
        r"nosotros\s+(?:vs\.?|versus|contra|o)\s+ellos",
        # Falso dilema "o estás con X o estás con Y" (con el pueblo /
        # con la patria / con nosotros, contra el régimen / la casta).
        r"o\s+est[áa]s?\s+con\s+.{1,25}?\s+o\s+(?:est[áa]s?\s+)?con",
        r"con\s+(?:el\s+pueblo|la\s+patria|nosotros)\s+o\s+con",
        # "el sistema/la élite/la casta" SOLO cuando el verbo revela la
        # oposición (te tienen, te controla, está en contra), no cuando
        # es un sustantivo neutro ("sistema de transporte", "élite
        # deportiva"). Evita el falso positivo de portales de noticias.
        r"(?:el\s+sistema|la\s+[ée]lite|la\s+casta)\s+(?:te|nos|los|las|me)\s+\w+",
        r"(?:el\s+sistema|la\s+[ée]lite|la\s+casta)\s+(?:est[áa]\s+en\s+contra|quiere\s+(?:que|verte)|no\s+quiere)",
        # Totalizadores de conflicto (mantienen la firma polarizante).
        r"todos\s+est[áa]n\s+en\s+(?:tu\s+)?contra",
        r"los\s+verdaderos\s+culpables\s+son",
        r"el\s+(?:r[ée]gimen|sistema)\s+corrupto",
        r"el\s+silencio\s+es\s+complicidad",
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