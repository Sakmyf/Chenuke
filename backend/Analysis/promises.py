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

# Promesa de enriquecimiento / scam de inversión. No busca frases fijas sino la
# ESTRUCTURA del fraude financiero: invitación a ganar/invertir dinero + gatillo
# de acción + (opcional) cifra deslumbrante. Esto captura landings de estafa que
# fraseolan distinto ("empezá a invertir y a ganar", "calculá tus ingresos
# potenciales") y que NO caen en contexto ecommerce (no piden CBU todavía).
WEALTH_LURE = [
    r"\b(empez(á|a|ar)|comenz(á|a|ar)|start)\b[^.]{0,40}\b(invertir|ganar|invest|earn)\b",
    r"\b(ganar|gana|hacer|generar)\b[^.]{0,20}\bdinero\b",
    r"\bingresos? (potenciales?|pasivos?|extra|garantizados?)\b",
    r"\bgan(á|a|e) (hasta|más de)\b[^.]{0,20}(\$|usd|dólares|euros|€)",
    r"\b(obtené|obtene|consigue|conseguí)\b[^.]{0,40}\b(beneficios?|ganancias?|rendimiento)\b",
    r"\bmake money\b", r"\bpassive income\b", r"\bget rich\b",
]
URGENCY_LURE = [
    r"\bno esperes\b", r"\bno pierdas (esta|la) oportunidad\b", r"\búltima oportunidad\b",
    r"\bsolo por hoy\b", r"\bcupos? limitados?\b", r"\bact now\b", r"\bdon'?t wait\b",
    r"\bempez(á|a) (ya|ahora|hoy)\b", r"\bahora mismo\b",
]
BIG_FIGURE = [
    r"\b\d{1,3}([.,]\d{3})+\s*(dólares|usd|euros|pesos|millones)",
    r"\b\d+\s*mil(es)?\s*(de\s*)?(millones|dólares|usd|pesos)",
    r"\b(mil|diez mil|cien mil|un millón)\s*(de\s*)?(dólares|millones|usd)",
]

def check_promises(text: str) -> RuleResult:
    result = RuleResult()
    t = (text or "").lower()
    matched = [p for p in PROMISE_PATTERNS if re.search(p, t)]
    if matched:
        result.points += min(0.8 + (len(matched) - 1) * 0.1, 1.0)
        result.reasons.append("exaggerated_promises")
        result.evidence.append(f"Promesa absoluta detectada ({len(matched)} señales)")

    # --- Detección de scam de enriquecimiento ---
    has_wealth = any(re.search(p, t) for p in WEALTH_LURE)
    has_urgency = any(re.search(p, t) for p in URGENCY_LURE)
    has_figure = any(re.search(p, t) for p in BIG_FIGURE)
    if has_wealth:
        # Invitación a ganar dinero ya es señal. Si además hay urgencia o una
        # cifra deslumbrante, el patrón de estafa de inversión es inequívoco.
        lure_score = 0.45
        lure_signals = ["Invitación a ganar/invertir dinero"]
        if has_urgency:
            lure_score += 0.30
            lure_signals.append("urgencia de acción")
        if has_figure:
            lure_score += 0.25
            lure_signals.append("cifra deslumbrante")
        result.points += min(lure_score, 1.0)
        result.reasons.append("wealth_lure_pattern")
        result.evidence.append("Patrón de promesa de enriquecimiento: " + ", ".join(lure_signals))
    return result

def analyze(text: str):
    return check_promises(text)
