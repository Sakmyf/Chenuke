"""credibility — Detección de lenguaje emocional, dramatización y estructura narrativa."""

from __future__ import annotations

from typing import Final

# --- Señales de emocionalidad ---

# Palabras emocionales cargadas (usadas en el score y en el conteo de adjetivos).
EMOTIONAL_WORDS: Final[tuple[str, ...]] = (
    "increible", "increíble", "impactante", "brutal", "terrible",
    "impresionante", "explota", "escandalo", "escándalo", "shock",
    "indignacion", "indignación", "caos", "furia",
)

# Frases dramáticas: narrativa de impacto personal.
DRAMA_PHRASES: Final[tuple[str, ...]] = (
    "no podia creer", "no podía creer", "quedo en shock", "quedó en shock",
    "dejo paralizada", "dejó paralizada", "genero caos", "generó caos",
    "nadie lo esperaba", "todo cambio", "todo cambió",
    "situacion tensa", "situación tensa",
)

# Indicadores de estructura narrativa (cuenta una historia, no informa).
NARRATIVE_MARKERS: Final[tuple[str, ...]] = (
    "con esta frase", "lo que parecia", "lo que parecía",
    "en ese momento", "de repente", "finalmente",
    "dentro de este relato",
)

# --- Umbrales ---

EMOTION_PER_HIT: float = 0.10
EMOTION_CAP: float = 0.40
DRAMA_PER_HIT: float = 0.15
DRAMA_CAP: float = 0.40
NARRATIVE_SCORE: float = 0.20
LONG_SENTENCE_SCORE: float = 0.15
LONG_SENTENCE_MIN: int = 2
LONG_SENTENCE_MIN_WORDS: int = 20
ADJECTIVE_MIN_HITS: int = 2
ADJECTIVE_SCORE: float = 0.15
WORD_COUNT_FOR_ADJECTIVE: int = 2


def analyze(text: str) -> dict:
    if not text:
        return {"score": 0.0, "signals": [], "reasons": [], "evidence": []}

    t = text.lower()
    score = 0.0
    signals: list[str] = []

    # 1) Palabras emocionales
    emotion_hits = sum(1 for w in EMOTIONAL_WORDS if w in t)
    if emotion_hits:
        score += min(EMOTION_PER_HIT * emotion_hits, EMOTION_CAP)
        signals.append("lenguaje emocional")

    # 2) Frases dramáticas
    drama_hits = sum(1 for p in DRAMA_PHRASES if p in t)
    if drama_hits:
        score += min(DRAMA_PER_HIT * drama_hits, DRAMA_CAP)
        signals.append("dramatizacion")

    # 3) Estructura narrativa
    if any(p in t for p in NARRATIVE_MARKERS):
        score += NARRATIVE_SCORE
        signals.append("estructura narrativa")

    # 4) Oraciones largas (narrativa extensa)
    long_sentences = [s for s in text.split(".") if len(s.split()) > LONG_SENTENCE_MIN_WORDS]
    if len(long_sentences) >= LONG_SENTENCE_MIN:
        score += LONG_SENTENCE_SCORE
        signals.append("narrativa extensa")

    # 5) Exceso de adjetivos (reusa EMOTIONAL_WORDS, no duplica lista)
    adjective_hits = sum(1 for w in EMOTIONAL_WORDS if w in t)
    if adjective_hits >= ADJECTIVE_MIN_HITS:
        score += ADJECTIVE_SCORE
        signals.append("exceso de adjetivos")

    score = max(0.0, min(score, 1.0))

    return {
        "score": round(score, 2),
        "signals": signals,
        "reasons": signals,
        "evidence": signals,
    }