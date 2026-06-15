import re
from backend.Analysis.rules_types import RuleResult

SERIOUS_CLAIMS = [r"\bfraude\b", r"\bestafa\b", r"\bcorrupción\b", r"\bengaño\b", r"\bilegal\b"]
CONSPIRACY_PATTERNS = [r"no quieren que sepas", r"te están ocultando", r"nadie habla de", r"verdad oculta"]
CATEGORICAL_PATTERNS = [r"es un hecho", r"está probado", r"sin dudas", r"queda demostrado"]
ATTRIBUTION_PATTERNS = [r"según", r"dijo", r"informó", r"declaró", r"reportó", r"informe", r"de acuerdo con"]

def check_misinformation(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    serious_found = [c for c in SERIOUS_CLAIMS if re.search(c, t)]
    if serious_found and not any(re.search(a, t) for a in ATTRIBUTION_PATTERNS):
        result.points += 0.9
        result.reasons.append("serious_accusation_without_source")
        result.evidence.append(f"Acusación grave sin fuente: {', '.join(serious_found)}")
    conspiracies = [p for p in CONSPIRACY_PATTERNS if re.search(p, t)]
    if conspiracies:
        result.points += 0.8
        result.reasons.append("conspiracy_language")
        result.evidence.append("Lenguaje conspirativo detectado")
    categorical = [p for p in CATEGORICAL_PATTERNS if re.search(p, t)]
    if categorical:
        result.points += 0.6
        result.reasons.append("categorical_claim")
        result.evidence.append("Afirmación categórica fuerte")
    return result

def analyze(text: str):
    return check_misinformation(text)