import re
from backend.Analysis.rules_types import RuleResult

URGENCY_KEYWORDS = [
    r"urgente", r"ahora", r"ya", r"inmediato", r"rápido",
    r"oferta", r"promoción", r"descuento", r"oportunidad", r"gane"
]
URGENCY_PATTERNS = [
    r"última oportunidad", r"actu[aá] ahora", r"antes (de )?que lo borren",
    r"solo\s+por\s+hoy", r"tiempo\s+limitado", r"decisión\s+inmediata"
]

def check_urgency(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    matches = sum(2 for p in URGENCY_PATTERNS if re.search(p, t))
    matches += sum(1 for w in URGENCY_KEYWORDS if w in t)
    if matches:
        result.points += min(0.9, matches * 0.15)
        result.reasons.append("urgency_pressure")
        result.evidence.append(f"Señales de urgencia detectadas: {matches}")
    return result

def analyze(text: str):
    return check_urgency(text)
