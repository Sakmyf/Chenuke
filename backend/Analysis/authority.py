"""authority — Detección de autoridad difusa vs. concreta en fuentes citadas."""

from __future__ import annotations

from typing import Final

# Señales de autoridad VAGA: invocan "expertos" sin nombrar quién.
WEAK_AUTHORITY: Final[tuple[str, ...]] = (
    "expertos dicen", "científicos aseguran", "especialistas afirman", "según expertos",
)

# Señales de autoridad CONCRETA: citan un referente identificable.
STRONG_AUTHORITY: Final[tuple[str, ...]] = (
    "dr.", "doctor", "profesor", "universidad", "instituto",
)


def analyze_authority(text: str) -> dict:
    if not text:
        return {"score": 0.0, "trust_bonus": 0.0, "signals": [], "evidence": []}

    t = text.lower()
    found_weak = [p for p in WEAK_AUTHORITY if p in t]
    found_strong = [p for p in STRONG_AUTHORITY if p in t]

    score = 0.0
    trust_bonus = 0.0
    signals: list[str] = []
    evidence: list[str] = []

    if found_weak and not found_strong:
        score = 0.25
        signals.append("weak_authority")
        evidence.append(f"Autoridad difusa sin referente concreto: {', '.join(found_weak)}")

    if found_strong and not found_weak:
        trust_bonus = 0.15
        signals.append("strong_authority")
        evidence.append(f"Referencia a autoridad concreta: {', '.join(found_strong[:2])}")
    elif found_strong and found_weak:
        trust_bonus = 0.08
        signals.append("mixed_authority")
        evidence.append("Mezcla de autoridad difusa y concreta")

    # dict.fromkeys preserva orden y dedupa
    return {
        "score": round(score, 2),
        "trust_bonus": round(trust_bonus, 2),
        "signals": list(dict.fromkeys(signals)),
        "evidence": list(dict.fromkeys(evidence)),
    }


def analyze(text: str) -> dict:
    return analyze_authority(text)