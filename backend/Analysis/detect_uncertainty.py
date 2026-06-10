import re
from backend.Analysis.rules_types import RuleResult

NUMBER_PATTERNS = [r"\b\d+[\.,]?\d*\s*(mil|millones?|billones?|personas?|empleos?|puestos?|casos?|muertes?|contagios?)\b", r"\b\d+\s*%", r"\b\d+\s*de\s*cada\s*\d+\b"]
STRONG_SOURCES = [r"\bindec\b", r"\bcepal\b", r"\boms\b", r"\bministerio\b", r"\bgobierno\b", r"\boficial\b", r"\bestadística\b"]
WEAK_SOURCES = [r"\bestudio\b", r"\binforme\b", r"\bdatos\b", r"\bsegún\b", r"\bfuentes\b"]
CONDITIONAL_PATTERNS = [r"\bhabría\b", r"\bhabrían\b", r"\bsería\b", r"\bserían\b", r"\bestaría\b", r"\bestarían\b", r"\bpodría\b", r"\bpodrían\b", r"\btrascendió\b", r"\bse especula\b"]
CATEGORICAL_UNVERIFIED = [r"\bes el peor\b", r"\bes el mejor\b", r"\bnunca antes\b", r"\bjamás\b", r"\bhistórico\b", r"\bsin precedentes\b", r"\bla mayor\b", r"\bla menor\b", r"\bcompletamente\b", r"\btotalmente\b"]
RECENCY_PATTERNS = [r"\bhoy\b", r"\bayer\b", r"\banoche\b", r"\besta\s+mañana\b", r"\bhoras\s+atrás\b", r"\bminutos\s+atrás\b"]

def detect_uncertainty(text: str, title: str = "", context: str = "general") -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    title_lower = (title or "").lower()
    if context in ["ecommerce", "product", "landing"]:
        return result
    multiplier = 0.3 if context in ["government", "institutional"] else 1.0 if context in ["news", "news_media"] else 0.6
    score = 0.0
    has_strong = any(re.search(p, t) for p in STRONG_SOURCES)
    has_weak = any(re.search(p, t) for p in WEAK_SOURCES)
    has_numbers = any(re.search(p, t) for p in NUMBER_PATTERNS)
    if has_numbers and not has_strong:
        score += 0.10 if has_weak else 0.25
        result.reasons.append("numbers_without_strong_source")
        result.evidence.append("Datos numéricos sin fuente sólida")
    conditional_count = sum(len(re.findall(p, t)) for p in CONDITIONAL_PATTERNS)
    allowed = int(max(1.0, len(text or "") / 1000.0) * 3)
    if conditional_count > allowed:
        score += min(0.3, (conditional_count - allowed) * 0.05)
        result.reasons.append("excessive_conditional_language")
        result.evidence.append(f"Uso excesivo de condicionales ({conditional_count}, esperado max {allowed})")
    categorical = [p for p in CATEGORICAL_UNVERIFIED if re.search(p, t)]
    if categorical and not has_strong:
        score += 0.20
        result.reasons.append("unverified_categorical_claim")
        result.evidence.append("Afirmación categórica sin respaldo")
    recency = [p for p in RECENCY_PATTERNS if re.search(p, t)]
    if recency and (categorical or has_numbers) and not has_strong:
        score += 0.15
        result.reasons.append("recent_unattributed_claim")
        result.evidence.append("Hecho reciente sin atribución clara")
    if title_lower:
        title_strong = any(re.search(p, title_lower) for p in CATEGORICAL_UNVERIFIED + NUMBER_PATTERNS)
        body_supports = has_strong or sum(1 for p in WEAK_SOURCES if re.search(p, t)) >= 2
        if title_strong and not body_supports:
            score += 0.20
            result.reasons.append("title_body_gap")
            result.evidence.append("El titular no está respaldado por el contenido")
    result.points = round(min(score * multiplier, 0.45), 3)
    result.reasons = list(dict.fromkeys(result.reasons))
    result.evidence = list(dict.fromkeys(result.evidence))
    return result

def analyze(text: str, title: str = "", context: str = "general"):
    return detect_uncertainty(text, title, context)
