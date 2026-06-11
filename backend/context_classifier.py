"""
context_classifier v2.0 — Clasificación ESTRUCTURAL del tipo de página.

Filosofía (CONTEXT.md): "analiza la estructura, no el contenido".

El clasificador v1 decidía por dominio (.gob → institucional). Eso es lineal y
frágil: no escala a las miles de variantes de TLD del mundo, y un boletín
oficial en un .com quedaba mal clasificado mientras una estafa en un dominio
gubernamental hackeado se salvaba por la etiqueta.

v2 invierte la lógica: lee CÓMO ESTÁ CONSTRUIDA la página (densidad de texto,
proporción de navegación, presencia de afirmaciones, estructura de párrafos,
señales comerciales) e infiere qué TIPO de página es —portada, artículo,
comercial, social— igual que una persona lo nota de un vistazo.

El dominio se usa solo como PISTA secundaria para casos inequívocos
(mercadolibre, facebook), nunca como decisión principal.

Salida: una de
  ecommerce | social | fact_check | institutional | news_media |
  landing | health_science | general
"""

import re
from urllib.parse import urlparse

# --- Pistas de dominio (secundarias, solo casos inequívocos) ---
_ECOMMERCE_DOMAINS = ("mercadolibre", "amazon", "ebay", "aliexpress", "tiendanube")
_SOCIAL_DOMAINS = ("facebook", "instagram", "tiktok", "twitter", "x.com", "threads", "reddit")
_FACTCHECK_DOMAINS = ("chequeado", "maldita", "snopes", "factcheck", "newtral")


def _host(url: str) -> str:
    try:
        h = urlparse(url if "://" in url else f"http://{url}").netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _host_matches(host: str, needles) -> bool:
    """Match por componente de host, no por substring suelto.
    Evita que 'x.com' matchee en 'diario-x.com' o 'instagram' en 'fake-instagram-news.com'."""
    if not host:
        return False
    for n in needles:
        # dominio completo (x.com) → debe ser el host o terminar en .x.com
        if "." in n:
            if host == n or host.endswith("." + n):
                return True
        # marca suelta (facebook) → debe ser una etiqueta del host
        elif n in host.split("."):
            return True
    return False

# --- Señales estructurales (léxicas, agnósticas de dominio) ---
_NAV_TOKENS = ("inicio", "contacto", "menú", "menu", "quiénes somos", "quienes somos",
               "servicios", "productos", "nosotros", "home", "iniciar sesión", "registrarse",
               "buscar", "categorías", "categorias", "ayuda", "soporte")
_COMMERCE_TOKENS = ("comprar", "carrito", "precio", "oferta", "descuento", "envío", "envio",
                    "pagar", "presupuesto", "cotización", "cotizacion", "stock", "agregar al carrito")
_ATTRIBUTION_TOKENS = ("informó", "informo", "reportó", "reporto", "según", "declaró", "declaro",
                       "afirmó", "afirmo", "publicó", "publico", "anunció", "anuncio", "confirmó")
_FIRST_PERSON = ("yo ", "mi ", "nosotros", "te cuento", "les comparto", "mira esto", "no van a creer")
_HEALTH_TOKENS = ("salud", "médico", "medico", "medicina", "científico", "cientifico",
                  "clínico", "clinico", "cura", "tratamiento", "síntomas", "sintomas", "vacuna")
_INSTITUTIONAL_TOKENS = ("ministerio", "secretaría", "secretaria", "municipalidad", "boletín oficial",
                         "boletin oficial", "resolución", "resolucion", "decreto", "organismo",
                         "ente", "dirección general", "direccion general", "gobierno", "oficial")


def _structure_profile(text: str):
    """Mide rasgos estructurales del texto."""
    t = (text or "")
    low = t.lower()
    length = len(t)
    words = low.split()
    word_count = len(words)

    nav_hits = sum(1 for tok in _NAV_TOKENS if tok in low)
    commerce_hits = sum(1 for tok in _COMMERCE_TOKENS if tok in low)
    attribution_hits = sum(1 for tok in _ATTRIBUTION_TOKENS if tok in low)
    health_hits = sum(1 for tok in _HEALTH_TOKENS if tok in low)
    institutional_hits = sum(1 for tok in _INSTITUTIONAL_TOKENS if tok in low)
    first_person_hits = sum(1 for tok in _FIRST_PERSON if tok in low)

    # Densidad de párrafos: texto corrido vs. lista de enlaces/navegación.
    sentences = [s for s in re.split(r"[.!?]+", t) if len(s.strip()) > 40]
    prose_ratio = len(sentences) / max(word_count / 20, 1)

    return {
        "length": length, "word_count": word_count,
        "nav_hits": nav_hits, "commerce_hits": commerce_hits,
        "attribution_hits": attribution_hits, "health_hits": health_hits,
        "institutional_hits": institutional_hits, "first_person_hits": first_person_hits,
        "prose_ratio": prose_ratio, "long_sentences": len(sentences),
    }


def classify_context(text: str, url: str = "") -> str:
    host = _host(url)
    u = (url or "").lower()

    # 1) Pistas de dominio inequívocas (no requieren análisis estructural).
    if _host_matches(host, _ECOMMERCE_DOMAINS):
        return "ecommerce"
    if _host_matches(host, _SOCIAL_DOMAINS):
        return "social"
    if _host_matches(host, _FACTCHECK_DOMAINS):
        return "fact_check"

    p = _structure_profile(text)

    # 2) PORTADA / LANDING: navegación dominante, poco texto corrido, sin
    #    afirmaciones atribuidas. Una home cae acá por su FORMA, sin mirar dominio.
    #    Pero NO debe tragarse una nota corta: si hay atribuciones o muchos
    #    números, hay contenido real que evaluar → no es landing.
    has_real_content = p["attribution_hits"] >= 2 or p["institutional_hits"] >= 2
    if p["long_sentences"] <= 2 and not has_real_content and (p["nav_hits"] >= 2 or p["length"] < 600):
        return "landing"

    # 3) COMERCIAL: señales de compra dominan el cuerpo.
    if p["commerce_hits"] >= 3 and p["commerce_hits"] > p["attribution_hits"]:
        return "ecommerce"

    # 4) INSTITUCIONAL vs 5) PERIODISMO — ambos son prosa con afirmaciones.
    #    Se decide por qué señal DOMINA, no por orden fijo:
    #    - normativa/organismo (resolución, decreto, ministerio) → institucional
    #    - atribución de dichos (informó, declaró, según) → periodismo
    inst = p["institutional_hits"]
    attr = p["attribution_hits"]
    if p["long_sentences"] >= 3 and (inst >= 2 or attr >= 2):
        return "institutional" if inst > attr else "news_media"

    # 6) SALUD/CIENCIA: temática médica con cuerpo de texto.
    if p["health_hits"] >= 2 and p["long_sentences"] >= 2:
        return "health_science"

    # 7) Respaldo por dominio para institucional (pista débil, último recurso).
    if any(host.endswith(tld) or tld + "." in host for tld in (".gob", ".gov", ".edu", ".int")):
        return "institutional"

    return "general"
