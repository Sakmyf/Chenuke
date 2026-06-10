import re
from backend.Analysis.rules_types import RuleResult

PROMISE_PATTERNS = [
    r"\bganancia segura\b", r"\bsin riesgo\b", r"\b100 ?% garantizado\b",
    r"\brendimiento garantizado\b", r"\bbeneficio asegurado\b",
    r"\bresultados garantizados\b", r"\béxito garantizado\b", r"\bsin esfuerzo\b",
    r"\bvida eterna\b", r"\bcura definitiva\b",
    r"\bguaranteed results?\b", r"\bno risk\b", r"\brisk.?free\b",
    r"\b100 ?% guaranteed\b", r"\bguaranteed (income|profit|return|benefit)\b",
    r"\blive (longer|forever|your longest)\b", r"\breverse aging\b",
    r"\banti.?aging (breakthrough|solution|cure)\b", r"\bscience.?backed\b",
]

def check_promises(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    matched = [p for p in PROMISE_PATTERNS if re.search(p, t)]
    if matched:
        result.points += min(0.8 + (len(matched) - 1) * 0.1, 1.0)
        result.reasons.append("exaggerated_promises")
        result.evidence.append(f"Promesa absoluta detectada ({len(matched)} señales)")
    return result

def analyze(text: str):
    return check_promises(text)
