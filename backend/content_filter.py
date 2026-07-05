"""content_filter.py — Filtro de contenido explícito (privacidad por diseño).

Propósito ético (ETHICS.md §2.4 — Privacidad como derecho):
Cuando el usuario navega contenido sexual/adulto, Chenuke NO debe analizarlo,
NO debe almacenar la URL en cache ni en logs, ni dejar rastro alguno de esa visita.
La minimización de datos prima sobre la cobertura del análisis.

Esto NO es censura ni juicio moral sobre el contenido: el sistema simplemente se
abstiene de procesar y registrar páginas íntimas del usuario. Devuelve un estado
neutral de "no analizado" sin score de riesgo.

Decisión deliberada: dominio O señales léxicas. No basta whitelist de dominios
porque hay miles; las señales léxicas cubren el resto sin guardar la URL.
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Dominios adultos frecuentes (LATAM + internacionales).
# Lista no exhaustiva: el detector léxico cubre el resto.
# Solo se usa el host, nunca se loguea la URL.
# ---------------------------------------------------------------------------

_ADULT_DOMAINS: Final[frozenset[str]] = frozenset({
    "pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com",
    "redtube.com", "youporn.com", "tube8.com", "spankbang.com",
    "chaturbate.com", "stripchat.com", "bongacams.com", "cam4.com",
    "livejasmin.com", "myfreecams.com", "camsoda.com",
    "onlyfans.com", "fansly.com",
    "brazzers.com", "bangbros.com", "realitykings.com", "naughtyamerica.com",
    "eporner.com", "hqporner.com", "porntrex.com", "beeg.com",
    "tnaflix.com", "porndig.com", "motherless.com", "rule34.xxx",
    "e621.net", "nhentai.net", "hanime.tv", "hentaihaven.xxx",
    "sexo.com", "serviporno.com", "petardas.com", "poringa.net",
    "cerdas.com", "pelisporno.net", "vlxx.com", "javhd.com",
})

# TLDs exclusivamente adultos
_ADULT_TLDS: Final[frozenset[str]] = frozenset({
    ".xxx", ".porn", ".adult", ".sex", ".sexy", ".cam", ".tube",
})

# ---------------------------------------------------------------------------
# Detector léxico: términos que en conjunto indican página adulta.
# Umbral por acumulación — un término aislado no dispara el filtro
# (evita falsos positivos en noticias, salud sexual, educación).
# ---------------------------------------------------------------------------

_LEXICAL_PATTERNS: Final[tuple[re.Pattern, ...]] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bporn(?:o|ograf[ií]a)?\b",
        r"\bxxx\b",
        r"\bsexo\s+(?:gratis|en\s+vivo|amateur|casero)\b",
        r"\bvideos?\s+porno\b",
        r"\bwebcams?\s+(?:eróticas?|adultas?|xxx|sexo)\b",
        r"\bcam\s*girls?\b",
        r"\bescorts?\b",
        r"\bhentai\b",
        r"\bmilf\b",
        r"\bamateur\s+sex\b",
        r"\bhardcore\b",
        r"\banal\b",
        r"\bblowjob\b",
        r"\bcumshot\b",
        r"\bgangbang\b",
        r"\bfetiche?s?\b",
        r"\bbdsm\b",
        r"\b18\+\s*(?:only|solo|contenido)\b",
        r"\bcontenido\s+(?:para\s+)?adultos?\b",
        r"\badult\s+content\b",
        r"\bage\s+verification\b.{0,40}\b18\b",
    )
)

# Cantidad mínima de patrones léxicos distintos para considerar la página adulta.
# 3+ coincidencias distintas = altísima probabilidad; 1-2 puede ser una noticia.
_LEXICAL_THRESHOLD: Final[int] = 3

# Patrones que en el TÍTULO son suficientes por sí solos (peso doble)
_TITLE_STRONG: Final[tuple[re.Pattern, ...]] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bporn(?:o)?\b",
        r"\bxxx\b",
        r"\bhentai\b",
        r"\bsexo\s+(?:gratis|en\s+vivo)\b",
    )
)


def _host_from_url(url: str) -> str:
    """Extrae el host de una URL sin loguearla. Devuelve '' si no parsea."""
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower()
        # Quitar puerto y www.
        host = host.split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _domain_is_adult(host: str) -> bool:
    if not host:
        return False

    # Match exacto o subdominio de un dominio conocido
    for domain in _ADULT_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return True

    # TLD exclusivamente adulto
    for tld in _ADULT_TLDS:
        if host.endswith(tld):
            return True

    return False


def _lexical_is_adult(title: str, text: str) -> bool:
    # Título con patrón fuerte → suficiente
    t = title or ""
    for pat in _TITLE_STRONG:
        if pat.search(t):
            return True

    # Acumulación en título + primeros 3000 chars del cuerpo
    sample = f"{t} {(text or '')[:3000]}"
    hits = 0

    for pat in _LEXICAL_PATTERNS:
        if pat.search(sample):
            hits += 1
            if hits >= _LEXICAL_THRESHOLD:
                return True

    return False


def is_explicit_content(url: str = "", title: str = "", text: str = "") -> bool:
    """True si la página es contenido adulto/explícito.

    El caller debe abstenerse de analizar, cachear y loguear.
    Determinístico: mismo input → mismo output. No registra nada.
    """
    host = _host_from_url(url)

    if _domain_is_adult(host):
        return True

    return _lexical_is_adult(title, text)