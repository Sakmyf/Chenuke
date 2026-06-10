def adjust_weights(base_weights: dict, context: str, source_info: dict) -> dict:
    weights = base_weights.copy()
    trust = source_info.get("trust_level", 0.55)
    if context == "health_science":
        weights["scientific_claims"] = weights.get("scientific_claims", 0.08) * 1.5
        weights["authority"] = weights.get("authority", 0.10) * 1.3
        weights["emotions"] = weights.get("emotions", 0.12) * 0.7
    elif context == "politics":
        weights["polarization"] = weights.get("polarization", 0.12) * 1.4
        weights["misinformation"] = weights.get("misinformation", 0.10) * 1.2
        weights["emotions"] = weights.get("emotions", 0.12) * 1.1
    elif context == "opinion":
        weights["emotions"] = weights.get("emotions", 0.12) * 0.6
        weights["polarization"] = weights.get("polarization", 0.12) * 0.7
    elif context in ("news", "news_media"):
        weights["credibility"] = weights.get("credibility", 0.15) * 0.7
    if trust > 0.8:
        weights["credibility"] = weights.get("credibility", 0.15) * 0.6
        weights["misinformation"] = weights.get("misinformation", 0.10) * 0.7
    elif trust < 0.4:
        weights["credibility"] = weights.get("credibility", 0.15) * 1.3
        weights["misinformation"] = weights.get("misinformation", 0.10) * 1.3
        weights["hypothetical"] = weights.get("hypothetical", 0.05) * 1.2
    return weights

def normalize_scores(scores: dict) -> dict:
    normalized = {}
    for k, v in scores.items():
        try: normalized[k] = max(0.0, float(v))
        except Exception: normalized[k] = 0.0
    return normalized
