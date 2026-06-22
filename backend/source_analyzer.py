"""Análisis de fuente — clasifica dominios y detecta señales mediáticas."""

from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Final

# ---------------------------------------------------------------------------
# Utilidades de URL
# ---------------------------------------------------------------------------

def _extract_hostname(url: str) -> str:
    """Extrae el hostname limpio de una URL, tolerando URLs sin scheme."""
    raw = url if (url or "").startswith("http") else "https://" + (url or "")
    try:
        return (urlparse(raw.lower()).hostname or "").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Dominios por categoría (sets para lookup O(1))
# ---------------------------------------------------------------------------

_INSTITUTIONAL_TLDS: Final[frozenset[str]] = frozenset({
    ".gov", ".gob", ".gov.ar", ".gob.ar", ".edu", ".edu.ar", ".int", ".org.ar",
})

_INSTITUTIONAL_DOMAINS: Final[frozenset[str]] = frozenset({
    "who.int", "un.org", "unesco.org", "paho.org",
    "worldbank.org", "imf.org",
    "chequeado.com", "snopes.com", "factcheck.org", "maldita.es",
})

_SOCIAL_DOMAINS: Final[frozenset[str]] = frozenset({
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "tiktok.com", "youtube.com", "t.me", "reddit.com",
    "threads.net", "whatsapp.com", "linkedin.com",
    "bsky.social", "mastodon.social",
})

_COMMERCIAL_DOMAINS: Final[frozenset[str]] = frozenset({
    "mercadolibre.com", "mercadopago.com",
    "amazon.com", "amazon.com.br", "amazon.com.mx",
    "ebay.com", "aliexpress.com", "falabella.com", "fravega.com",
})

_SHORTENER_DOMAINS: Final[frozenset[str]] = frozenset({
    "bit.ly", "tinyurl.com", "ow.ly", "buff.ly",
})

_SUSPICIOUS_TLDS: Final[frozenset[str]] = frozenset({
    ".xyz", ".click", ".top", ".tk", ".ml", ".ga", ".cf", ".buzz", ".icu", ".monster",
})

# Nota: `t.co` (acortador de X/Twitter) se excluye de shorteners.
# Todo link compartido en X pasa por t.co; marcarlo como suspicious
# penalizaría injustamente contenido legítimo. Se detecta como social
# vía el dominio original (x.com / twitter.com).

_NEWS_DOMAINS: Final[frozenset[str]] = frozenset({
    # Argentina
    "lanacion.com.ar", "clarin.com", "pagina12.com.ar", "infobae.com",
    "perfil.com", "lacapital.com.ar", "cronista.com", "ambito.com",
    "telam.com.ar",
    # Internacional (español/general)
    "elpais.com", "eltiempo.com", "eluniverso.com", "bbc.com",
    "reuters.com", "apnews.com", "nytimes.com", "washingtonpost.com",
    "theguardian.com", "lemonde.fr",
})


# ---------------------------------------------------------------------------
# Detección de tipo de fuente
# ---------------------------------------------------------------------------

def _matches_domain(hostname: str, domains: frozenset[str]) -> bool:
    """True si hostname es exactamente un dominio o un subdominio del mismo."""
    if hostname in domains:
        return True
    # host = "sub.example.com" → ".example.com" debe estar en domains
    # pero "notexample.com" NO debe coincidir con "example.com"
    dot_host = "." + hostname
    return any(dot_host.endswith("." + d) for d in domains)


def _detect_source_type(hostname: str) -> str:
    """Clasifica un hostname en una categoría de fuente."""
    if any(hostname.endswith(tld) for tld in _INSTITUTIONAL_TLDS):
        return "institutional"
    if _matches_domain(hostname, _INSTITUTIONAL_DOMAINS):
        return "institutional"
    if _matches_domain(hostname, _NEWS_DOMAINS):
        return "news"
    if _matches_domain(hostname, _SOCIAL_DOMAINS):
        return "social"
    if _matches_domain(hostname, _COMMERCIAL_DOMAINS):
        return "commercial"
    if any(hostname.endswith(tld) for tld in _SUSPICIOUS_TLDS):
        return "suspicious"
    if _matches_domain(hostname, _SHORTENER_DOMAINS):
        return "suspicious"
    return "unknown"


# ---------------------------------------------------------------------------
# Detección de señales mediáticas en el texto
# ---------------------------------------------------------------------------

# Precompilados: se compilan UNA VEZ al importar el módulo.
_REPORT_VERBS: Final[list[re.Pattern]] = [
    re.compile(p) for p in (
        r"\bdeclaró\b", r"\binformó\b", r"\bsegún\b", r"\breportó\b",
        r"\bafirmó\b", r"\bseñaló\b", r"\bconfirmó\b", r"\bindicó\b",
        r"\baseguró\b", r"\bde acuerdo con\b",
    )
]

_RE_ATTRIBUTION = re.compile(r"\bpor\s+[A-ZÁÉÍÓÚ][a-záéíóú]+\b")
_RE_MONTHS = re.compile(
    r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto"
    r"|septiembre|octubre|noviembre|diciembre)\b",
)
_RE_SECTIONS = re.compile(
    r"\b(política|economía|sociedad|deportes|internacional"
    r"|cultura|tecnología|salud|judiciales)\b",
)


def _detect_media_signals(text: str) -> bool:
    """Detecta si el texto tiene señales estilísticas de contenido periodístico."""
    if not text:
        return False

    t = text.lower()
    signals = 0

    if sum(1 for p in _REPORT_VERBS if p.search(t)) >= 2:
        signals += 1
    if _RE_ATTRIBUTION.search(text):
        signals += 1
    if _RE_MONTHS.search(t):
        signals += 1
    if _RE_SECTIONS.search(t):
        signals += 1
    if text.count('"') >= 2 or text.count("«") >= 1:
        signals += 1

    return signals >= 3


# ---------------------------------------------------------------------------
# Configuración por tipo de fuente
# ---------------------------------------------------------------------------

_SOURCE_CONFIG: Final[dict[str, dict]] = {
    "institutional": {
        "trust_level": 0.90,
        "message": "Fuente institucional verificable",
        "signals": ["fuente institucional verificable"],
    },
    "news": {
        "trust_level": 0.70,
        "message": "Medio periodístico — puede tener sesgo editorial",
        "signals": ["medio periodístico detectado"],
    },
    "media": {
        "trust_level": 0.65,
        "message": "Contenido periodístico — puede tener sesgo editorial",
        "signals": ["medio periodístico detectado"],
    },
    "commercial": {
        "trust_level": 0.55,
        "message": "Contenido comercial — orientado a persuadir la compra",
        "signals": ["contenido comercial — persuasión esperada"],
    },
    "unknown": {
        "trust_level": 0.55,
        "message": "Fuente no categorizada — leé con atención",
        "signals": [],
    },
    "social": {
        "trust_level": 0.30,
        "message": "Contenido en red social — sin verificación editorial",
        "signals": ["red social — sin proceso editorial"],
    },
    "suspicious": {
        "trust_level": 0.15,
        "message": "Dominio de baja confianza — alto escrutinio recomendado",
        "signals": ["dominio o acortador de baja confianza"],
    },
}


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def analyze_source(url: str, text: str = "") -> dict:
    """Clasifica la fuente de una URL y, opcionalmente, detecta señales mediáticas en el texto.

    Returns:
        dict con keys: domain, trust_level, type, message, signals.
    """
    hostname = _extract_hostname(url) if url else ""

    if not hostname:
        return {
            "domain": "",
            "trust_level": 0.55,
            "type": "unknown",
            "message": "Sin información de fuente",
            "signals": [],
        }

    source_type = _detect_source_type(hostname)

    # Si el dominio no se reconoció pero el texto pinta a periodístico
    if source_type == "unknown" and text and _detect_media_signals(text):
        source_type = "media"

    cfg = _SOURCE_CONFIG[source_type]
    return {
        "domain": hostname,
        "trust_level": cfg["trust_level"],
        "type": source_type,
        "message": cfg["message"],
        "signals": list(cfg["signals"]),
    }