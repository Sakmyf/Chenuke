def analyze_contradictions(text: str) -> dict:
    if not text:
        return {"score": 0.0, "signals": [], "reasons": [], "evidence": []}
    t = text.lower()
    neg = ["no hay evidencia", "no existe", "no está probado"]
    aff = ["está demostrado", "es un hecho", "comprobado"]
    found_neg = [p for p in neg if p in t]
    found_aff = [p for p in aff if p in t]
    if found_neg and found_aff:
        ev = f"Posible contradicción: negación ({found_neg[0]}) + afirmación ({found_aff[0]})"
        return {"score": 0.8, "signals": ["internal_contradiction"], "reasons": ["internal_contradiction"], "evidence": [ev]}
    return {"score": 0.0, "signals": [], "reasons": [], "evidence": []}

def analyze(text: str):
    return analyze_contradictions(text)
