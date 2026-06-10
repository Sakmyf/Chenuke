import re
from backend.Analysis.rules_types import RuleResult

ABSOLUTES = [r"\btodos\b", r"\bnadie\b", r"\bsiempre\b", r"\bnunca\b"]
CLICKBAIT_PATTERNS = [r"no vas a creer", r"lo que pasó después", r"te sorprenderá", r"impactante", r"increíble"]

def check_structural(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    text_length = len(text or "")
    text_length_k = max(1.0, text_length / 1000.0)
    allowed = int(text_length_k * 4)
    absolute_count = sum(len(re.findall(p, t)) for p in ABSOLUTES)
    if absolute_count > allowed:
        excess = absolute_count - allowed
        result.points += min(0.8, excess * 0.1)
        result.reasons.append("absolute_generalization")
        result.evidence.append(f"Uso desproporcionado de generalizaciones ({absolute_count}, esperado max {allowed})")
    clickbait = [p for p in CLICKBAIT_PATTERNS if re.search(p, t)]
    if clickbait:
        result.points += min(0.7, len(clickbait) * 0.2)
        result.reasons.append("clickbait_structure")
        result.evidence.append(f"Patrones clickbait detectados: {', '.join(clickbait)}")
    uppercase_ratio = sum(1 for c in (text or "") if c.isupper()) / max(text_length, 1)
    if uppercase_ratio > 0.25 and text_length > 30:
        result.points += 0.6
        result.reasons.append("excessive_uppercase")
        result.evidence.append(f"Uso excesivo de mayúsculas ({int(uppercase_ratio * 100)}%)")
    return result

def analyze(text: str):
    return check_structural(text)
