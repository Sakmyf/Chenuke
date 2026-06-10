from dataclasses import dataclass, field
from typing import List

@dataclass
class RuleResult:
    """Resultado estándar: points positivo = riesgo."""
    points: float = 0.0
    reasons: List[str] = field(default_factory=list)
    critical: bool = False
    evidence: List[str] = field(default_factory=list)
