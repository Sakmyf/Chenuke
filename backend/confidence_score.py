"""confidence_score.py — Confianza del análisis.

Mide qué tan confiable es el resultado del motor según dos dimensiones:
1. Intensidad promedio: ¿los módulos que se dispararon lo hicieron con fuerza?
2. Consistencia: ¿cuántos módulos se dispararon? Más módulos de acuerdo
   = más confianza en que el resultado no es un falso positivo aislado.

Rango de salida: [0.20, 1.00]
"""

from __future__ import annotations

# La base garantiza un mínimo de confianza (20%) para evitar que un
# resultado legítimo se marque como "no confiable" solo porque un módulo
# dio score bajo. El piso de 0.25 cuando ningún módulo se disparó refleja
# que el motor no encontró señales pero no puede garantizarlo con fuerza.
_CONFIDENCE_BASE: float = 0.20
_CONFIDENCE_NO_SIGNALS_FLOOR: float = 0.25

# Peso de cada dimensión en la fórmula final.
_WEIGHT_INTENSITY: float = 0.50   # avg de scores positivos
_WEIGHT_CONSISTENCY: float = 0.30  # proporción de módulos que se dispararon
# El resto (0.20) es la base.

# Módulos positivos necesarios para considerar la consistencia "completa".
# Con 13 módulos totales, 5+ de acuerdo es masa crítica suficiente.
_CONSISTENCY_SATURATION: float = 5.0


def compute_confidence(module_results: dict[str, float]) -> float:
    """Calcula la confianza del análisis a partir de los scores por módulo.

    Args:
        module_results: {nombre_modulo: score} donde cada score está en [0, 1].

    Returns:
        float en [0.20, 1.00] indicando la confianza del resultado.
    """
    if not module_results:
        return 0.0

    positives = [v for v in module_results.values() if v > 0]

    if not positives:
        return _CONFIDENCE_NO_SIGNALS_FLOOR

    avg = sum(positives) / len(positives)
    consistency = min(len(positives) / _CONSISTENCY_SATURATION, 1.0)

    return round(
        min(_CONFIDENCE_BASE + avg * _WEIGHT_INTENSITY + consistency * _WEIGHT_CONSISTENCY, 1.0),
        2,
    )