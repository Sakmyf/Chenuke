def analyze(text: str):
    lower = (text or "").lower()
    score = 0.0; reasons = []; evidence = []
    conspirative = ["lo que no quieren que sepas", "la verdad que nadie dice", "esto no te lo van a mostrar", "los medios lo ocultan", "compartí antes que lo borren", "esto será eliminado", "los poderosos no quieren", "te están mintiendo", "la verdad oculta", "nadie habla de esto"]
    m = [p for p in conspirative if p in lower]
    if m: score += 0.6; reasons.append("conspiracy_narrative"); evidence.extend(m)
    drama = ["escena imaginada", "recreación", "según versiones", "tras la carrera", "lo que parecía", "se volvió", "ola imparable", "cargada de", "incapaz de", "imagined scene", "recreation", "as if", "could have", "would have said"]
    md = [p for p in drama if p in lower]
    if len(md) >= 2: score += 0.5; reasons.append("dramatized_structure"); evidence.extend(md)
    rec = ["escena", "relato", "imaginada", "reconstrucción", "recreación", "versiones", "ficción", "ficticio", "narrativa", "según la recreación"]
    mr = [p for p in rec if p in lower]
    if len(mr) >= 2: score += 0.6; reasons.append("unverified_reconstruction"); evidence.extend(mr)
    if "dramatized_structure" in reasons and "unverified_reconstruction" in reasons:
        score += 0.3; reasons.append("fictional_narrative_with_real_context")
    connectors = ["y aunque", "sin embargo", "entonces", "finalmente"]
    if sum(1 for c in connectors if c in lower) >= 5:
        score += 0.2; reasons.append("narrative_sequence")
    return {"score": round(min(score, 1.0), 2), "reasons": list(dict.fromkeys(reasons)), "evidence": list(dict.fromkeys(evidence))}
