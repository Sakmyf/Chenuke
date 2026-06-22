"""contradictions — Detección de contradicciones internas (negación + afirmación)."""

from __future__ import annotations

from typing import Final

NEGATION_PHRASES: Final[tuple[str, ...]] = (
    "no hay evidencia", "no existe", "no está probado",
)

AFFIRMATION_PHRASES: Final[tuple[str, ...]] = (
    "está demostrado", "es un hecho", "comprobado",
)

CONTRADICTION_SCORE: float = 0.8


def analyze_contradictions(text: str) -> dict:
    if not text:
        return {"score": 0.0, "signals": [], "reasons": [], "evidence": []}

    t = text.lower()
    found_neg = [p for p in NEGATION_PHRASES if p in t]
    found_aff = [p for p in AFFIRMATION_PHRASES if p in t]

    if found_neg and found_aff:
        ev = (
            f"Posible contradicción: negación ({found_neg[0]}) "
            f"+ afirmación ({found_aff[0]})"
        )
        return {
            "score": CONTRADICTION_SCORE,
            "signals": ["internal_contradiction"],
            "reasons": ["internal_contradiction"],
            "evidence": [ev],
        }

    return {"score": 0.0, "signals": [], "reasons": [], "evidence": []}


def analyze(text: str) -> dict:
    return analyze_contradictions(text)