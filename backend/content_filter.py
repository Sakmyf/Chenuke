"""
content_filter.py — Filtro de contenido explícito (privacidad por diseño).

Propósito ético (ETHICS.md §2.4 — Privacidad como derecho):
Cuando el usuario navega contenido sexual/adulto, SignalCheck NO debe analizarlo,
NO debe almacenar la URL en cache ni en logs, ni dejar rastro alguno de esa visita.
La minimización de datos prima sobre la cobertura del análisis.

Esto NO es censura ni juicio moral sobre el contenido: el sistema simplemente se
abstiene de procesar y registrar páginas íntimas del usuario. Devuelve un estado
neutral de "no analizado" sin score de riesgo.

Decisión deliberada: dominio O señales léxicas. No basta whitelist de dominios
porque hay miles; las señales léxicas cubren el resto sin guardar la URL.
"""

import re
from urllib.parse import urlparse

# Dominios adultos frecuentes (LATAM + internacionales). Lista no exhaustiva:
# el detector léxico cubre el resto. Solo se usa el host, nunca se loguea la URL.
_ADULT_DOMAINS = frozenset({
    "pornhub.com", "xvideos.com", "xnxx.com", "redtube.com", "youporn.com",
    "xhamster.com", "spankbang.com", "poringa.net", "superporn.com",
    "chaturbate.com", "onlyfans.com", "stripchat.com", "brazzers.com",
    "rule34.xxx", "e-hentai.org", "nhentai.net", "fakings.com",
})

# TLDs casi siempre asociados a contenido adulto.
_ADULT_TLDS = (".xxx", ".porn", ".sex", ".adult", ".cam")

# Señales léxicas: contenido sexual explícito. Se evalúan sobre title + muestra
# corta del texto. Pensadas para es-AR + inglés. Umbral: 2+ señales distintas.
_ADULT_LEXICON = re.compile(
    r"(?i)\b("
    r"porno?|pornstar|xxx|hardcore|hentai|camgirl|webcam\s+sex|"
    r"sexo\s+(?:explícito|explicito|anal|oral|gratis)|"
    r"folla(?:r|ndo|da)|coger\s+rico|tetona|culona|cachonda|"
    r"masturb(?:a|ándose|andose)|corrida|squirt|milf|"
    r"desnud(?:a|o|os|as)\s|nude|naked\s+girl|"
    r"escort|trans\s+xxx|onlyfans"
    r")\b"
)


def _normalize_host(url: str) -> str:
    try:
        host = urlparse(url if "://" in url else f"http://{url}").netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def is_explicit_content(url: str = "", title: str = "", text: str = "") -> bool:
    """
    True si la página es contenido sexual explícito y debe omitirse del análisis.

    Capa 1 — dominio/TLD: corte inmediato sin mirar el texto.
    Capa 2 — léxico: 2+ señales distintas en title + primeros 1500 chars.
    """
    host = _normalize_host(url)
    if host:
        if host in _ADULT_DOMAINS or any(host.endswith("." + d) for d in _ADULT_DOMAINS):
            return True
        if any(host.endswith(tld) for tld in _ADULT_TLDS):
            return True

    sample = f"{title}\n{text[:1500]}"
    matches = set(m.group(0).lower() for m in _ADULT_LEXICON.finditer(sample))
    return len(matches) >= 2
