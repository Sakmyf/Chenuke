def classify_context(text: str, url: str = ""):
    t = (text or "").lower(); u = (url or "").lower()
    if any(d in u for d in ["mercadolibre", "amazon", "ebay"]): return "ecommerce"
    if any(d in u for d in ["facebook", "instagram", "tiktok", "twitter", "x.com"]): return "social"
    if any(d in u for d in ["chequeado", "maldita", "snopes"]): return "fact_check"
    if any(d in u for d in [".gob", ".gov", ".edu"]): return "institutional"
    if any(w in t for w in ["salud", "médico", "medicina", "científico", "clínico", "cura"]): return "health_science"
    if any(w in t for w in ["informó", "reportó", "según"]): return "news_media"
    return "general"
