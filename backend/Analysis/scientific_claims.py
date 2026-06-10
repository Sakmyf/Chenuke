import re
from backend.Analysis.rules_types import RuleResult

MEDICAL_KEYWORDS = [
    r"\bcura\b", r"\bcurar\b", r"tratamiento definitivo", r"100 ?% efectivo",
    r"comprobado científicamente", r"reemplaza la medicina", r"la medicina no quiere que sepas",
    r"avalado por médicos", r"científicamente probado", r"sin efectos secundarios", r"cura definitiva",
    r"\bcure[sd]?\b", r"100 ?% effective", r"scientifically (proven|backed|validated)",
    r"science.?backed", r"clinically proven", r"doctors (don.?t want|hate)",
    r"(extend|reverse|stop) aging", r"miracle (cure|solution|treatment)",
]
SUPPORT_INDICATORS = ["estudio", "ensayo clínico", "universidad", "revista científica", "publicado en", "journal", "investigación", "study", "clinical trial", "published in", "research", "according to", "nih", "who"]

def check_scientific_claims(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    matches = [p for p in MEDICAL_KEYWORDS if re.search(p, t)]
    if matches:
        has_support = any(re.search(ind, t) for ind in SUPPORT_INDICATORS)
        if not has_support:
            result.points += min(0.7 + (len(matches) - 1) * 0.1, 1.0)
            result.reasons.append("unsupported_scientific_claim")
            result.evidence.append(f"Afirmación científica/salud sin respaldo ({len(matches)} señales)")
        elif len(matches) >= 3:
            result.points += 0.2
            result.reasons.append("multiple_health_claims_with_partial_support")
    return result

def analyze(text: str):
    return check_scientific_claims(text)
