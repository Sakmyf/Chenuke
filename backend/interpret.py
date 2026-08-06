# interpret.py — Capa de interpretación de Chénuke
# Traduce (level + signals del motor) a lenguaje interpretativo, SIN dictaminar.
# Regla ETHICS 2.2: describe el PATRÓN del mensaje, nunca ordena qué hacer con ÉL.

from typing import List, Dict

# --- Mapa module -> frase (describe patrón, 3ra persona, nunca imperativo) ---
# Claves = valores REALES del campo "module" (BASE_WEIGHTS de engine.py).
SENALES = {
    "urgency":            "presiona para que actúes rápido",
    "emotions":           "usa carga emocional para convencer",
    "promises":           "hace promesas fuertes o desproporcionadas",
    "authority":          "invoca autoridad o prestigio sin respaldo claro",
    "contradictions":     "presenta afirmaciones que no cierran entre sí",
    "polarization":       "usa lenguaje que divide o polariza",
    "misinformation":     "hace afirmaciones fuertes sin fuente visible",
    "scientific_claims":  "afirma cosas de ciencia o salud sin respaldo visible",
    "narrative_patterns": "arma una estructura narrativa dramatizada o novelada",
    "hypothetical":       "presenta lo hipotético como si fuera un hecho",
    "structural":         "usa una estructura tipo clickbait o titular engañoso",
    "logical_fallacies":  "recurre a falacias lógicas (falso dilema, ataque personal)",
    "commercial_risk":    "tiene una intención comercial poco explícita",
    # credibility NO mide credibilidad ni evidencia: detecta TONO dramático/
    # narrativo (lenguaje emocional, dramatización, oraciones largas). La frase
    # describe eso. Ver regla anti-duplicado con `emotions` más abajo.
    "credibility":        "está escrito con un tono dramático o novelado",
}

# Módulos de AUSENCIA de respaldo -> van al cierre, no a la lista principal.
# 'uncertainty' agrupa: datos sin fuente, condicionales excesivos, afirmaciones
# sin respaldo, hechos recientes sin atribución. (credibility NO va acá.)
EVIDENCIA = {"uncertainty"}

# Módulos cuyo ángulo es emocional. Si dispara más de uno, se usa UNA sola frase
# (la del primero que aparezca) para no decir dos veces "carga emocional".
_EMOCIONALES = {"emotions", "credibility"}

# --- Cierre por nivel (reducción de daño GENÉRICA, nunca veredicto del mensaje) ---
_CIERRE = {
    "bajo":  "Son señales leves. Igual conviene leerlo con atención.",
    "medio": "Es un patrón frecuente en mensajes que buscan que actúes sin pensarlo. "
             "No lo vuelve falso, pero conviene mirarlo dos veces.",
    "alto":  "Es un patrón muy asociado a mensajes manipuladores. No afirma que sea falso, "
             "pero conviene verificar por fuera antes de tomar cualquier decisión.",
}

_PREGUNTAS = [
    "¿Quién firma este mensaje?",
    "¿Cita alguna fuente que puedas comprobar?",
    "¿Por qué te apura?",
    "¿Qué gana quien lo escribió si actuás?",
]


def _unir(frases):
    frases = list(frases)
    if not frases:
        return ""
    if len(frases) == 1:
        return frases[0]
    return ", ".join(frases[:-1]) + " y " + frases[-1]


def interpretar(level: str, signals: List[Dict], max_senales: int = 3) -> dict:
    """
    level:   'bajo' | 'medio' | 'alto'
    signals: array tal cual lo devuelve el motor -> [{"label","detail","module"}, ...]
    return:  {'resumen': str, 'preguntas': [str]}
    """
    level = (level or "bajo").lower()

    manip, sin_evidencia = [], False
    emocional_usado = False

    for s in signals or []:
        mod = s.get("module")

        if mod in EVIDENCIA:
            sin_evidencia = True
            continue

        if mod not in SENALES:
            continue

        # Anti-duplicado emocional: emotions y credibility comparten el ángulo
        # "carga emocional". Solo el primero aporta su frase; el segundo se omite.
        if mod in _EMOCIONALES:
            if emocional_usado:
                continue
            emocional_usado = True

        frase = SENALES[mod]
        if frase not in manip and len(manip) < max_senales:
            manip.append(frase)

    if manip:
        cuerpo = "Este texto " + _unir(manip)
        if sin_evidencia:
            cuerpo += ", con poca evidencia verificable"
        cuerpo += ". "
    elif sin_evidencia:
        cuerpo = "Este texto ofrece poca evidencia verificable. "
    else:
        cuerpo = ("No se detectaron señales estructurales fuertes: el texto presenta "
                  "la información sin presión ni promesas desproporcionadas evidentes. ")

    return {
        "resumen": cuerpo + _CIERRE.get(level, _CIERRE["bajo"]),
        "preguntas": list(_PREGUNTAS),
    }