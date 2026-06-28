"""Ajuste de pesos por contexto y confianza de fuente — Chenuke."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Umbrales de confianza
# ---------------------------------------------------------------------------

TRUST_HIGH_THRESHOLD = 0.8
TRUST_LOW_THRESHOLD = 0.4


# ---------------------------------------------------------------------------
# Factores de ajuste por contexto
# ---------------------------------------------------------------------------

_CONTEXT_MULTIPLIERS: dict[str, dict[str, float]] = {
    "health_science": {
        "scientific_claims": 1.5,
        "authority": 1.3,
        "emotions": 0.7,
    },

    "politics": {
        "polarization": 1.25,
        "misinformation": 1.15,
        "emotions": 0.95,
        "promises": 0.75,
    },

    "opinion": {
        "emotions": 0.6,
        "polarization": 0.7,
        "promises": 0.6,
        "narrative_patterns": 0.75,
    },

    "news": {
        # En noticias, una palabra como "inversión", "crisis" o "alianzas"
        # no debe disparar por sí sola riesgo comercial o promesas.
        "credibility": 0.7,
        "urgency": 0.75,
        "emotions": 0.70,
        "promises": 0.60,
        "narrative_patterns": 0.75,
        "uncertainty": 0.85,
    },

    "news_media": {
        "credibility": 0.7,
        "urgency": 0.75,
        "emotions": 0.70,
        "promises": 0.60,
        "narrative_patterns": 0.75,
        "uncertainty": 0.85,
    },

    "institutional": {
        "urgency": 0.40,
        "emotions": 0.40,
        "polarization": 0.40,
        "promises": 0.50,
        "narrative_patterns": 0.50,
        "hypothetical": 0.40,
        "misinformation": 0.25,
        "structural": 0.35,
    },

    "ecommerce": {
        "promises": 1.35,
        "urgency": 1.20,
        "credibility": 1.15,
        "polarization": 0.60,
        "narrative_patterns": 0.70,
    },

    "finance": {
        "promises": 1.25,
        "urgency": 1.15,
        "credibility": 1.10,
        "uncertainty": 1.10,
        "polarization": 0.70,
    },
}


# ---------------------------------------------------------------------------
# Factores de ajuste por nivel de confianza de la fuente
# ---------------------------------------------------------------------------

_TRUST_HIGH_MULTIPLIERS: dict[str, float] = {
    "credibility": 0.6,
    "misinformation": 0.7,
    "uncertainty": 0.85,
}

_TRUST_LOW_MULTIPLIERS: dict[str, float] = {
    "credibility": 1.3,
    "misinformation": 1.3,
    "hypothetical": 1.2,
    "uncertainty": 1.15,
}


def _apply_multipliers(
    weights: dict[str, float],
    multipliers: dict[str, float],
) -> None:
    """Aplica multiplicadores in-place sobre los pesos existentes."""
    for key, factor in multipliers.items():
        if key in weights:
            weights[key] *= factor


def _renormalize(weights: dict[str, float]) -> dict[str, float]:
    """Escala todos los pesos para que sumen 1.0."""
    total = sum(weights.values())

    if total == 0:
        return weights

    return {
        key: value / total
        for key, value in weights.items()
    }


def adjust_weights(
    base_weights: dict[str, float],
    context: str,
    source_info: dict,
) -> dict[str, float]:
    """Ajusta los pesos base según contexto y confianza de fuente."""
    weights = base_weights.copy()
    trust = float(source_info.get("trust_level", 0.55))

    context_mults = _CONTEXT_MULTIPLIERS.get(context)

    if context_mults is not None:
        _apply_multipliers(weights, context_mults)

    if trust > TRUST_HIGH_THRESHOLD:
        _apply_multipliers(weights, _TRUST_HIGH_MULTIPLIERS)

    elif trust < TRUST_LOW_THRESHOLD:
        _apply_multipliers(weights, _TRUST_LOW_MULTIPLIERS)

    return _renormalize(weights)


def normalize_scores(scores: dict) -> dict:
    """Clamp simple de scores individuales."""
    return {
        key: max(0.0, float(value))
        for key, value in scores.items()
        if value is not None
    }