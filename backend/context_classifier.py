"""context_classifier v2.1 — Clasificación ESTRUCTURAL del tipo de página.

Filosofía (CONTEXT.md): "analiza la estructura, no el contenido".

v2 invierte la lógica del v1: lee CÓMO ESTÁ CONSTRUIDA la página (densidad
de texto, proporción de navegación, presencia de afirmaciones, señales
comerciales) e infiere qué TIPO de página es.

El dominio se usa solo como PISTA secundaria para casos inequívocos
(mercadolibre, facebook), nunca como decisión principal.

Salida: una de
  ecommerce | social | fact_check | institutional | news_media | news |
  politics | opinion | landing | health_science | general
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Pistas de dominio (secundarias, solo casos inequívocos)
# ---------------------------------------------------------------------------

_ECOMMERCE_DOMAINS: Final[tuple[str, ...]] = (
    "mercadolibre", "amazon", "ebay", "aliexpress", "tiendanube",
)
_SOCIAL_DOMAINS: Final[tuple[str, ...]] = (
    "facebook", "instagram", "tiktok", "twitter", "x.com", "threads", "reddit",
)
_FACTCHECK_DOMAINS: Final[tuple[str, ...]] = (
    "chequeado", "maldita", "snopes", "factcheck", "newtral",
)
_NEWS_DOMAINS: Final[tuple[str, ...]] = (
    "lanacion.com.ar", "clarin.com", "pagina12.com.ar", "infobae.com",
    "perfil.com", "cronista.com", "ambito.com", "telam.com.ar",
    "elpais.com", "eltiempo.com", "reuters.com", "apnews.com",
    "bbc.com", "nytimes.com", "washingtonpost.com", "theguardian.com",
)

_INSTITUTIONAL_TLDS: Final[tuple[str, ...]] = (
    ".gob.ar", ".gov.ar", ".edu.ar", ".gob", ".gov", ".edu", ".int", ".org.ar",
)

# ---------------------------------------------------------------------------
# Señales estructurales (léxicas, agnósticas de dominio)
# ---------------------------------------------------------------------------

_NAV_TOKENS: Final[tuple[str, ...]] = (
    "inicio", "contacto", "menú", "menu", "quiénes somos", "quienes somos",
    "servicios", "productos", "nosotros", "home", "iniciar sesión", "registrarse",
    "buscar", "categorías", "categorias", "ayuda", "soporte",
)

_COMMERCE_TOKENS: Final[tuple[str, ...]] = (
    "comprar", "carrito", "precio", "oferta", "descuento", "envío", "envio",
    "pagar", "presupuesto", "cotización", "cotizacion", "stock", "agregar al carrito",
)

_ATTRIBUTION_TOKENS: Final[tuple[str, ...]] = (
    "informó", "informo", "reportó", "reporto", "según", "declaró", "declaro",
    "afirmó", "afirmo", "publicó", "publico", "anunció", "anuncio", "confirmó",
)

_HEALTH_TOKENS: Final[tuple[str, ...]] = (
    "salud", "médico", "medico", "medicina", "científico", "cientifico",
    "clínico", "clinico", "cura", "tratamiento", "síntomas", "sintomas", "vacuna",
)

_INSTITUTIONAL_TOKENS: Final[tuple[str, ...]] = (
    "ministerio", "secretaría", "secretaria", "municipalidad", "boletín oficial",
    "boletin oficial", "resolución", "resolucion", "decreto", "organismo",
    "ente", "dirección general", "direccion general", "gobierno", "oficial",
)

# --- Nuevos: opinión y política ---

_OPINION_TOKENS: Final[tuple[str, ...]] = (
    "creo que", "opino que", "mi opinión", "mi opinion", "a mi entender",
    "desde mi punto de vista", "personalmente", "me parece", "considero que",
    "estoy convencido", "estoy convencida", "defiendo que", "pienso que",
    "la verdad es que", "sinceramente", "honestamente", "me gustaría",
)

_POLITICS_TOKENS: Final[tuple[str, ...]] = (
    "elecciones", "candidato", "candidata", "gobierno", "oposición", "oposicion",
    "diputado", "diputada", "senador", "senadora", "legislativo", "ley ",
    "proyecto de ley", "votación", "votacion", "parlamento", "congreso",
    "partido político", "partido politico", "coalición", "coalicion",
    "presidente", "ministra", "ministro", "funcionario", "funcionaria",
)

# --- Primera persona: usa word boundaries en vez de substrings literales ---
_RE_FIRST_PERSON = re.compile(
    r"\b(yo|mis|míos|mías|nuestro|nuestra|nuestros|nuestras|nosotros|nosotras)\b",
    re.IGNORECASE,
)

# --- Preguntas retóricas (señal de opinión/editorial) ---
_RE_QUESTION_DENSITY = re.compile(r"\?")


# ---------------------------------------------------------------------------
# Utilidades de host
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    try:
        h = urlparse(url if "://" in url else f"http://{url}").netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _host_matches(host: str, needles: tuple[str, ...]) -> bool:
    """Match por componente de host, no por substring suelto.
    Evita que 'x.com' matchee en 'diario-x.com'."""
    if not host:
        return False
    for n in needles:
        if "." in n:
            if host == n or host.endswith("." + n):
                return True
        elif n in host.split("."):
            return True
    return False


# ---------------------------------------------------------------------------
# Perfil estructural
# ---------------------------------------------------------------------------

_RE_SENTENCE_SPLIT = re.compile(r"[.!?]+")


def _structure_profile(text: str) -> dict:
    """Mide rasgos estructurales del texto."""
    t = text or ""
    low = t.lower()
    words = low.split()
    word_count = len(words)

    nav_hits = sum(1 for tok in _NAV_TOKENS if tok in low)
    commerce_hits = sum(1 for tok in _COMMERCE_TOKENS if tok in low)
    attribution_hits = sum(1 for tok in _ATTRIBUTION_TOKENS if tok in low)
    health_hits = sum(1 for tok in _HEALTH_TOKENS if tok in low)
    institutional_hits = sum(1 for tok in _INSTITUTIONAL_TOKENS if tok in low)
    opinion_hits = sum(1 for tok in _OPINION_TOKENS if tok in low)
    politics_hits = sum(1 for tok in _POLITICS_TOKENS if tok in low)
    first_person_hits = len(_RE_FIRST_PERSON.findall(low))
    question_marks = len(_RE_QUESTION_DENSITY.findall(t))

    # Oraciones largas (>40 chars): proxy de prosa vs navegación.
    sentences = [s for s in _RE_SENTENCE_SPLIT.split(t) if len(s.strip()) > 40]
    prose_ratio = len(sentences) / max(word_count / 20, 1)

    return {
        "length": len(t),
        "word_count": word_count,
        "nav_hits": nav_hits,
        "commerce_hits": commerce_hits,
        "attribution_hits": attribution_hits,
        "health_hits": health_hits,
        "institutional_hits": institutional_hits,
        "opinion_hits": opinion_hits,
        "politics_hits": politics_hits,
        "first_person_hits": first_person_hits,
        "question_marks": question_marks,
        "prose_ratio": prose_ratio,
        "long_sentences": len(sentences),
    }


# ---------------------------------------------------------------------------
# Clasificador principal
# ---------------------------------------------------------------------------

def classify_context(text: str, url: str = "") -> str:
    """Clasifica el contexto estructural de una página.

    Prioridad:
    1. Dominios inequívocos (sin análisis)
    2. Señales estructurales fuertes (comercio, salud, institucional)
    3. Discriminación fina entre periodismo, política y opinión
    4. Default: general
    """
    host = _host(url)

    # --- 1) Pistas de dominio inequívocas ---
    if _host_matches(host, _ECOMMERCE_DOMAINS):
        return "ecommerce"
    if _host_matches(host, _SOCIAL_DOMAINS):
        return "social"
    if _host_matches(host, _FACTCHECK_DOMAINS):
        return "fact_check"

    # TLDs institucionales: registro controlado, sin necesidad de análisis.
    if any(host.endswith(tld) for tld in _INSTITUTIONAL_TLDS):
        return "institutional"

    # Dominios periodísticos conocidos → news (no news_media;
    # news_media se reserva para texto con señales periodísticas en dominio desconocido).
    if _host_matches(host, _NEWS_DOMAINS):
        return "news"

    p = _structure_profile(text)

    # --- 2) LANDING: navegación dominante, poco texto corrido ---
    has_real_content = (
        p["attribution_hits"] >= 2
        or p["institutional_hits"] >= 2
        or p["opinion_hits"] >= 2
        or p["politics_hits"] >= 2
    )
    if p["long_sentences"] <= 2 and not has_real_content and (p["nav_hits"] >= 2 or p["length"] < 600):
        return "landing"

    # --- 3) COMERCIAL: señales de compra dominan ---
    if p["commerce_hits"] >= 3 and p["commerce_hits"] > p["attribution_hits"]:
        return "ecommerce"

    # --- 4) SALUD/CIENCIA ---
    if p["health_hits"] >= 2 and p["long_sentences"] >= 2:
        return "health_science"

    # --- 5) Discriminación fina: institucional vs periodismo vs política vs opinión ---
    #    Todos son prosa con afirmaciones. Se decide por qué señal DOMINA.
    inst = p["institutional_hits"]
    attr = p["attribution_hits"]
    poli = p["politics_hits"]
    opin = p["opinion_hits"]
    fp = p["first_person_hits"]

    # 5a) Institucional: lenguaje normativo domina
    if p["long_sentences"] >= 3 and inst >= 2 and inst > attr and inst > poli:
        return "institutional"

    # 5b) Política: señales políticas dominan sobre opinión pura
    #     (una columna política tiene política + opinión; gana política)
    if p["long_sentences"] >= 3 and poli >= 2 and poli >= opin:
        # Con atribución fuerte → es noticia política, no opinión política
        if attr >= 3:
            return "news_media"
        return "politics"

    # 5c) Opinión: primera persona + lenguaje subjetivo, sin atribución fuerte
    if p["long_sentences"] >= 3 and (opin >= 2 or (fp >= 2 and p["question_marks"] >= 2)):
        if attr >= 3:
            return "news_media"  # entrevista o columna con muchas citas
        return "opinion"

    # 5d) Periodismo: atribución de dichos domina
    if p["long_sentences"] >= 3 and attr >= 2:
        return "news_media"

    # --- 6) SOCIAL detectado por estructura (no por dominio) ---
    #    Primera persona + preguntas + pocas oraciones largas → post
    if fp >= 3 and p["question_marks"] >= 1 and p["long_sentences"] <= 3:
        return "social"

    return "general"