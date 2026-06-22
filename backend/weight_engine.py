"""Ajuste de pesos por contexto y confianza de fuente — SignalCheck."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Umbrales de confianza
# ---------------------------------------------------------------------------
TRUST_HIGH_THRESHOLD = 0.8
TRUST_LOW_THRESHOLD = 0.4

# ---------------------------------------------------------------------------
# Factores de ajuste por contexto
# ---------------------------------------------------------------------------
# Cada key es el nombre del módulo; el valor es el multiplicador a aplicar.
# Los módulos NO listados aquí mantienen su peso base (factor = 1.0).
_CONTEXT_MULTIPLIERS: dict[str, dict[str, float]] = {
    "health_science": {
        "scientific_claims": 1.5,
        "authority": 1.3,
        "emotions": 0.7,
    },
    "politics": {
        "polarization": 1.4,
        "misinformation": 1.2,
        "emotions": 1.1,
    },
    "opinion": {
        "emotions": 0.6,
        "polarization": 0.7,
    },
    "news": {
        "credibility": 0.7,
    },
    "news_media": {
        "credibility": 0.7,
    },
    "institutional": {
        # Fuentes institucionales (.gob.ar, .edu, etc.): los módulos de
        # manipulación narrativa no aplican con el mismo peso. Un trámite
        # de gobierno usa "obligatoria", "necesitarás", "plazo", "condición"
        # por naturaleza — no son señales de riesgo en ese contexto.
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
        # En contexto comercial, la presión de compra y las promesas son
        # señales más relevantes que la polarización o la narrativa política.
        "promises": 1.3,
        "urgency": 1.2,
        "credibility": 1.15,
        "polarization": 0.6,
        "narrative_patterns": 0.7,
    },
}

# ---------------------------------------------------------------------------
# Factores de ajuste por nivel de confianza de la fuente
# ---------------------------------------------------------------------------
_TRUST_HIGH_MULTIPLIERS: dict[str, float] = {
    "credibility": 0.6,
    "misinformation": 0.7,
}

_TRUST_LOW_MULTIPLIERS: dict[str, float] = {
    "credibility": 1.3,
    "misinformation": 1.3,
    "hypothetical": 1.2,
}


def _apply_multipliers(weights: dict[str, float], multipliers: dict[str, float]) -> None:
    """Aplica multiplicadores in-place sobre los pesos existentes."""
    for key, factor in multipliers.items():
        if key in weights:
            weights[key] *= factor


def _renormalize(weights: dict[str, float]) -> dict[str, float]:
    """Escala todos los pesos para que sumen 1.0.

    Esto es crucial: sin renormalización, los ajustes contextuales
    pueden hacer que la suma de pesos sea >1 o <1, causando que el
    risk score final no esté acotado correctamente.
    """
    total = sum(weights.values())
    if total == 0:
        return weights
    return {k: v / total for k, v in weights.items()}


def adjust_weights(
    base_weights: dict[str, float],
    context: str,
    source_info: dict,
) -> dict[str, float]:
    """Ajusta los pesos base según contexto y confianza de la fuente.

    El proceso:
    1. Copia los pesos base.
    2. Aplica multiplicadores por contexto.
    3. Aplica multiplicadores por nivel de confianza.
    4. Renormaliza para que la suma siempre sea 1.0.
    """
    weights = base_weights.copy()
    trust = float(source_info.get("trust_level", 0.55))

    # 1) Ajuste por contexto
    context_mults = _CONTEXT_MULTIPLIERS.get(context)
    if context_mults is not None:
        _apply_multipliers(weights, context_mults)

    # 2) Ajuste por confianza
    if trust > TRUST_HIGH_THRESHOLD:
        _apply_multipliers(weights, _TRUST_HIGH_MULTIPLIERS)
    elif trust < TRUST_LOW_THRESHOLD:
        _apply_multipliers(weights, _TRUST_LOW_MULTIPLIERS)

    # 3) Renormalizar
    return _renormalize(weights)


def normalize_scores(scores: dict) -> dict:
    """Clamp de scores a [0.0, ∞). Usado por módulos individuales."""
    return {k: max(0.0, float(v)) for k, v in scores.items() if v is not None}