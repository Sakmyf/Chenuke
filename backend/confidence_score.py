def compute_confidence(module_results: dict):
    if not module_results: return 0.0
    positives = [v for v in module_results.values() if v > 0]
    if not positives: return 0.25
    avg = sum(positives) / len(positives)
    consistency = min(len(positives) / 5, 1.0)
    return round(min(0.2 + avg * 0.5 + consistency * 0.3, 1.0), 2)
