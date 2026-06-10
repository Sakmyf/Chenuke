def analyze(text: str):
    if not text:
        return {"score": 0.0, "signals": [], "reasons": [], "evidence": []}
    t = text.lower()
    score = 0.0; signals = []
    emotional_words = ["increible", "increíble", "impactante", "brutal", "terrible", "impresionante", "explota", "escandalo", "escándalo", "shock", "indignacion", "indignación", "caos", "furia"]
    hits = sum(1 for w in emotional_words if w in t)
    if hits:
        score += min(0.1 * hits, 0.4); signals.append("lenguaje emocional")
    drama = ["no podia creer", "no podía creer", "quedo en shock", "quedó en shock", "dejo paralizada", "dejó paralizada", "genero caos", "generó caos", "nadie lo esperaba", "todo cambio", "todo cambió", "situacion tensa", "situación tensa"]
    dhits = sum(1 for p in drama if p in t)
    if dhits:
        score += min(0.15 * dhits, 0.4); signals.append("dramatizacion")
    story = ["con esta frase", "lo que parecia", "lo que parecía", "en ese momento", "de repente", "finalmente", "dentro de este relato"]
    if any(p in t for p in story):
        score += 0.2; signals.append("estructura narrativa")
    long_sentences = [s for s in text.split(".") if len(s.split()) > 20]
    if len(long_sentences) >= 2:
        score += 0.15; signals.append("narrativa extensa")
    adjectives = ["increible", "increíble", "impactante", "terrible", "impresionante", "inesperado", "fuerte", "brutal"]
    if sum(1 for w in adjectives if w in t) >= 2:
        score += 0.15; signals.append("exceso de adjetivos")
    score = max(0.0, min(score, 1.0))
    return {"score": round(score, 2), "signals": signals, "reasons": signals, "evidence": signals}
