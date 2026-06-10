import re
from backend.Analysis.rules_types import RuleResult

HYPOTHETICAL_PATTERNS = [r"habría dicho", r"habría ocurrido", r"según trascendió", r"se comenta que", r"escena imaginada", r"fuentes cercanas", r"todo indicaría", r"aparentemente"]

def check_hypothetical(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    matches = [p for p in HYPOTHETICAL_PATTERNS if re.search(p, t)]
    if matches:
        result.points += 0.4
        result.reasons.append("hypothetical_or_unverified_claim")
        result.evidence.extend(matches)
    return result

def analyze(text: str):
    return check_hypothetical(text)
