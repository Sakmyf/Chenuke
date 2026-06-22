"""rules_types — Tipos estándar para los módulos de análisis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuleResult:
    """Resultado estándar de un módulo de análisis.

    points > 0 indica que el módulo detectó señales de riesgo.
    reasons = códigos internos que el engine mapea a SIGNAL_LABELS.
    evidence = texto legible para mostrar al usuario.
    critical = reservado para señales que ameriten tratamiento especial.
    """
    points: float = 0.0
    reasons: list[str] = field(default_factory=list)
    critical: bool = False
    evidence: list[str] = field(default_factory=list)


__all__ = ["RuleResult"]