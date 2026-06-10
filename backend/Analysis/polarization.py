import re
from backend.Analysis.rules_types import RuleResult

POLARIZATION_PATTERNS = [r"ellos vs nosotros", r"la élite", r"el sistema", r"todos están en contra", r"los verdaderos culpables"]
GENERALIZATION_PATTERNS = [r"\btodos\b", r"\bnadie\b", r"\bsiempre\b", r"\bnunca\b"]

def check_polarization(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    matches = 0
    for pattern in POLARIZATION_PATTERNS:
        if re.search(pattern, t):
            matches += 1
            result.evidence.append(f"Patrón polarizante detectado: {pattern}")
    generalizations = sum(len(re.findall(g, t)) for g in GENERALIZATION_PATTERNS)
    if matches:
        result.points += min(1.0, matches * 0.3)
        result.reasons.append("polarization_detected")
    if generalizations > 3:
        result.points += 0.3
        result.reasons.append("overgeneralization")
    return result

def analyze(text: str):
    return check_polarization(text)
