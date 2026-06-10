import re
from backend.Analysis.rules_types import RuleResult

EMOTION_PATTERNS = [
    r"cansado de", r"merecés", r"tu vida va a cambiar", r"libertad financiera", r"viví como soñás",
    r"impactante", r"alarmante", r"terrible", r"indignante", r"escandaloso"
]

def analyze(text: str) -> RuleResult:
    result = RuleResult()
    t = text or ""
    hits = [p for p in EMOTION_PATTERNS if re.search(p, t, re.I)]
    if hits:
        result.points += min(0.1 * len(hits), 0.7)
        result.reasons.append("manipulación emocional")
        result.evidence.extend(hits[:5])
    return result

def check_emotions(text: str):
    return analyze(text)
