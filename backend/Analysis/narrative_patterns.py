"""narrative_patterns — Detección de patrones narrativos manipuladores:
conspirativos, dramatizados, reconstrucciones no verificables, y ficción
aplicada a contexto real.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Señales por categoría
# ---------------------------------------------------------------------------

CONSPIRATIVE: Final[tuple[str, ...]] = (
    "lo que no quieren que sepas", "la verdad que nadie dice",
    "esto no te lo van a mostrar", "los medios lo ocultan",
    "compartí antes que lo borren", "esto será eliminado",
    "los poderosos no quieren", "te están mintiendo",
    "la verdad oculta", "nadie habla de esto",
)

# Frases que construyen una escena dramática (no necesariamente conspirativa).
DRAMATIC: Final[tuple[str, ...]] = (
    "escena imaginada", "recreación", "según versiones",
    "tras la carrera", "lo que parecía", "se volvió",
    "ola imparable", "cargada de", "incapaz de",
    "imagined scene", "recreation", "as if",
    "could have", "would have said",
)

# Palabras de reconstrucción/ficción aplicada a hechos reales.
RECONSTRUCTION: Final[tuple[str, ...]] = (
    "escena", "relato", "imaginada", "reconstrucción", "recreación",
    "versiones", "ficción", "ficticio", "narrativa", "según la recreación",
)

# Conectores narrativos (en cantidad anormal → estructura de cuento).
CONNECTORS: Final[tuple[str, ...]] = (
    "y aunque", "sin embargo", "entonces", "finalmente",
    "además", "mientras tanto", "de pronto", "en cambio",
)

# ---------------------------------------------------------------------------
# Umbrales
# ---------------------------------------------------------------------------

CONSPIRACY_SCORE: float = 0.6
DRAMA_MIN_HITS: int = 2
DRAMA_SCORE: float = 0.5
RECONSTRUCTION_MIN_HITS: int = 2
RECONSTRUCTION_SCORE: float = 0.6
COMBINED_BONUS: float = 0.3  # drama + reconstrucción → ficción con contexto real
CONNECTOR_THRESHOLD: int = 5  # FIX: antes era 5 con solo 4 items = imposible
CONNECTOR_SCORE: float = 0.2

# Nota: "recreación" aparece en DRAMATIC y RECONSTRUCTION. Se dedupa
# vía dict.fromkeys en el evidence final.


def analyze(text: str) -> dict:
    lower = (text or "").lower()
    score = 0.0
    reasons: list[str] = []
    evidence: list[str] = []

    # 1) Narrativa conspirativa
    consp = [p for p in CONSPIRATIVE if p in lower]
    if consp:
        score += CONSPIRACY_SCORE
        reasons.append("conspiracy_narrative")
        evidence.extend(consp)

    # 2) Estructura dramatizada
    drama = [p for p in DRAMATIC if p in lower]
    if len(drama) >= DRAMA_MIN_HITS:
        score += DRAMA_SCORE
        reasons.append("dramatized_structure")
        evidence.extend(drama)

    # 3) Reconstrucción no verificable
    recon = [p for p in RECONSTRUCTION if p in lower]
    if len(recon) >= RECONSTRUCTION_MIN_HITS:
        score += RECONSTRUCTION_SCORE
        reasons.append("unverified_reconstruction")
        evidence.extend(recon)

    # 4) Combinación: drama + reconstrucción → ficción aplicada a contexto real
    if "dramatized_structure" in reasons and "unverified_reconstruction" in reasons:
        score += COMBINED_BONUS
        reasons.append("fictional_narrative_with_real_context")

    # 5) Conectores narrativos (exceso = estructura de relato)
    connector_hits = sum(1 for c in CONNECTORS if c in lower)
    if connector_hits >= CONNECTOR_THRESHOLD:
        score += CONNECTOR_SCORE
        reasons.append("narrative_sequence")

    return {
        "score": round(min(score, 1.0), 2),
        "reasons": list(dict.fromkeys(reasons)),
        "evidence": list(dict.fromkeys(evidence)),
    }