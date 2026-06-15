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
    # Colapsar saltos de línea y espacios múltiples: las landings parten frases
    # en varias líneas ("Empieza a\ninvertir y a ganar dinero") y eso rompía el
    # matcheo de patrones que esperan secuencias en una línea continua.
    t = re.sub(r"\s+", " ", (text or "").lower()).strip()
    matched = [p for p in PROMISE_PATTERNS if re.search(p, t)]
    if matched:
        result.points += min(0.8 + (len(matched) - 1) * 0.1, 1.0)
        result.reasons.append("exaggerated_promises")
        result.evidence.append(f"Promesa absoluta detectada ({len(matched)} señales)")

    # --- Detección de scam de enriquecimiento ---
    # IMPORTANTE: "invertir", "dinero", "beneficios" son palabras del lenguaje
    # económico NORMAL. Una nota que explica "cuánto cuesta abrir una franquicia"
    # o una página de gobierno que ofrece "beneficios" NO es una estafa. El scam
    # real combina: invitación a ganar dinero fácil + GATILLO DE ACCIÓN URGENTE.
    # Por eso exigimos el núcleo (wealth) MÁS un acompañante, nunca wealth solo.
    has_wealth = any(re.search(p, t) for p in WEALTH_LURE)
    has_urgency = any(re.search(p, t) for p in URGENCY_LURE)
    has_figure = any(re.search(p, t) for p in BIG_FIGURE)
    # El núcleo "ganar dinero fácil" (sin contexto de costo/análisis) es lo que
    # distingue al scam. Frases como "ganar dinero desde tu casa", "ingresos
    # pasivos", "empezá a ganar" son la firma; "invertir para poner una franquicia"
    # no lo es. Requerimos núcleo fuerte + al menos un acompañante (urgencia/cifra).
    strong_wealth = any(re.search(p, t) for p in [
        r"\bingresos? (pasivos?|garantizados?)\b",
        r"\bingresos?\b[^.]{0,30}\b(a corto plazo|en \d+ (días?|semanas?|meses?))\b",
        r"\bcalcul(á|a)\b[^.]{0,25}\b(ingresos?|ganancias?)\b",      # "calcula tus ingresos potenciales"
        r"\b(ganar|gana|generar)\b[^.]{0,25}\bdinero\b[^.]{0,30}\b(casa|fácil|rápido|online|sin (salir|trabajar))\b",
        r"\bempez(á|a|ar)\b[^.]{0,15}\b(invertir|ganar|generar)\b[^.]{0,20}\bdinero\b",  # "empieza a invertir y a ganar dinero"
        r"\b(invertir|invest)\b[^.]{0,10}\b(y a |and )?(ganar|gana|earn)\b[^.]{0,15}\bdinero\b",
        r"\bingreso anual de\b",                                      # "beneficios del ingreso anual de Coca-Cola" (marca usurpada)
        r"\bempez(á|a) (ya|ahora|hoy)\b[^.]{0,30}\b(ganar|invertir|generar)\b",
        r"\b(monto|inversión) mínim[oa]\b[^.]{0,30}(\$|\d)",
        r"\bmake money\b", r"\bpassive income\b", r"\bget rich\b",
        r"\bgan(á|a|e) (hasta|más de)\b[^.]{0,20}(\$|usd|dólares|euros)",
    ])
    # Scam confirmado: núcleo fuerte de "dinero fácil" + acompañante de presión.
    is_wealth_scam = strong_wealth and (has_urgency or has_figure)
    if is_wealth_scam:
        lure_signals = ["Promesa de dinero fácil"]
        lure_score = 0.55
        if has_urgency: lure_signals.append("urgencia de acción")
        if has_figure: lure_signals.append("cifra deslumbrante")
        result.points += min(lure_score + 0.15, 1.0)
        result.reasons.append("wealth_lure_pattern")
        result.evidence.append("Patrón de promesa de enriquecimiento: " + ", ".join(lure_signals))
    elif has_wealth and (has_urgency and has_figure):
        # Señal más débil (wealth genérico) pero con DOBLE acompañante: sospechoso,
        # sin piso automático — suma puntos y deja que el resto del motor decida.
        result.points += 0.30
        result.reasons.append("possible_wealth_lure")
        result.evidence.append("Lenguaje de ganancia con urgencia y cifras — revisar")
    return result

def analyze(text: str):
    return check_promises(text)
