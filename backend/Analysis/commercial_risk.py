"""commercial_risk — Análisis de riesgo en páginas de e-commerce.

Filosofía (v15.15): el riesgo se basa EXCLUSIVAMENTE en señales estructurales
reales de fraude (TLD basura, login forzado, precio oculto, reviews falsas,
ausencia de legales, presión de pago). No se penaliza por dominio no
reconocido — una whitelist es inviable para LATAM.
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Dominios y TLDs
# ---------------------------------------------------------------------------

# Marcas mega-conocidas: solo para DESCUENTO extra, nunca para penalizar.
KNOWN_DOMAINS: Final[tuple[str, ...]] = (
    "mercadolibre", "amazon", "ebay", "fravega", "garbarino",
    "carrefour", "coto", "vecompras", "tevecompras",
)

# ccTLDs comerciales nacionales de LATAM: registro con trámite legal.
# Señal ESTRUCTURAL de legitimidad que escala sin necesidad de lista de nombres.
LATAM_COMMERCIAL_CCTLDS: Final[tuple[str, ...]] = (
    ".com.ar", ".com.mx", ".com.co", ".com.pe", ".com.br", ".com.uy",
    ".com.cl", ".com.bo", ".com.ec", ".com.py", ".com.gt", ".com.sv",
    ".com.hn", ".com.ni", ".com.cr", ".com.pa", ".com.do",
)

SUSPICIOUS_TLDS: Final[tuple[str, ...]] = (
    ".xyz", ".top", ".click", ".site", ".store", ".online",
)

# ---------------------------------------------------------------------------
# Señales de texto
# ---------------------------------------------------------------------------

HIGH_VALUE_PRODUCTS: Final[tuple[str, ...]] = (
    "iphone", "samsung", "macbook", "notebook", "playstation",
)

LOGIN_PATTERNS: Final[tuple[str, ...]] = (
    "iniciar sesión", "registrate", "crear cuenta", "acceder", "ver precios",
    "ingresar", "sign in", "log in", "login", "register", "create account",
)

PRICE_HIDDEN_PATTERNS: Final[tuple[str, ...]] = (
    "ver precio", "consultar precio", "precio no disponible",
)

LEGAL_PATTERNS: Final[tuple[str, ...]] = (
    "cuit", "razón social", "direccion", "dirección", "términos",
    "condiciones", "terms", "privacy policy", "legal",
)

# NOTA (v15.15): se quitaron tokens sueltos demasiado genéricos:
#   "disponible" → substring de "disponibles" (cupos/turnos/modalidades).
#   "agregar"    → palabra general; se mantiene "agregar al carrito".
#   "cart"       → substring de "carta", "cartel", "cartón".
#   "store"      → substring de "restorent" o nombres propios.
ECOMMERCE_TEXT_SIGNALS: Final[tuple[str, ...]] = (
    "comprar", "carrito", "oferta", "envío", "precio", "descuento",
    "tienda", "checkout", "pagar", "agregar al carrito", "añadir", "stock",
    "buy now", "shop now", "add to cart", "shipping", "price",
    "discount", "order now", "buy", "shop",
)

ECOMMERCE_URL_SIGNALS: Final[tuple[str, ...]] = (
    "shop", "store", "tienda", "compra", "cart", "checkout",
    "product", "oferta", "catalogo",
)

# ---------------------------------------------------------------------------
# Patrones regex (precompilados)
# ---------------------------------------------------------------------------

_GENERIC_REVIEWS_RE = re.compile(
    r"\d{3,} reviews|\d{3,} opiniones|\d{1,3},\d{3}\s*(?:task\s*)?reviews|\d{1,3},\d{3}",
)

_PAYMENT_PRESSURE_RE = re.compile(
    r"\bdepositá\b|\btransferí\b|\bcbu\b|\bcvu\b|\bclave token\b"
    r"|\benviar dinero\b|\bpago anticipado\b",
)

# ---------------------------------------------------------------------------
# Umbrales
# ---------------------------------------------------------------------------

MAX_RISK: float = 10.0
RISK_HIGH: float = 7.0
RISK_MEDIUM: float = 4.0
MAX_SIGNALS: int = 5

# Multiplicadores de descuento
KNOWN_DOMAIN_FACTOR: float = 0.5
LATAM_CCTLD_FACTOR: float = 0.7
INSTITUTIONAL_FACTOR: float = 0.4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_ecommerce_context(
    text: str, url: str = "", context: str = "general"
) -> bool:
    t = (text or "").lower()
    u = (url or "").lower()
    url_signal = any(w in u for w in ECOMMERCE_URL_SIGNALS)
    text_signal = any(w in t for w in ECOMMERCE_TEXT_SIGNALS)

    if context == "institutional":
        # Instituciones no son tiendas: exigimos URL explícita de tienda
        # o presión de pago real (CBU/transferencia).
        return url_signal or bool(_PAYMENT_PRESSURE_RE.search(t))

    return url_signal or text_signal


# ---------------------------------------------------------------------------
# Análisis principal
# ---------------------------------------------------------------------------

def analyze_commercial_risk(
    text: str, url: str = "", context: str = "general"
) -> dict:
    t = (text or "").lower()
    domain = extract_domain(url)

    if not is_ecommerce_context(text, url, context):
        return {"level": "none", "score": 0, "summary": "", "signals": []}

    risk = 0
    signals: list[str] = []

    # --- Señales de riesgo (suma puntual) ---
    if domain and any(tld in domain for tld in SUSPICIOUS_TLDS):
        risk += 3
        signals.append("TLD asociado a sitios de alto riesgo")

    if any(p in t for p in LOGIN_PATTERNS):
        risk += 3
        signals.append("Acceso restringido o login obligatorio")

    if any(p in t for p in PRICE_HIDDEN_PATTERNS):
        risk += 2
        signals.append("Información de precios no visible")

    if any(p in t for p in HIGH_VALUE_PRODUCTS):
        risk += 2
        signals.append("Producto de alto valor detectado")

    if _GENERIC_REVIEWS_RE.search(t):
        risk += 3
        signals.append("Patrones de reseñas potencialmente artificiales")

    if not any(k in t for k in LEGAL_PATTERNS):
        risk += 2
        signals.append("Ausencia de información legal identificable")

    # FIX: usar el regex precompilado en vez de re-search individual
    if _PAYMENT_PRESSURE_RE.search(t):
        risk += 4
        signals.append("Solicitud de transferencia o datos sensibles")

    # --- Descuentos estructurales (nunca penalizaciones) ---
    if domain and any(k in domain for k in KNOWN_DOMAINS):
        risk *= KNOWN_DOMAIN_FACTOR
    elif domain and any(domain.endswith(tld) for tld in LATAM_COMMERCIAL_CCTLDS):
        risk *= LATAM_CCTLD_FACTOR

    if context == "institutional":
        risk *= INSTITUTIONAL_FACTOR

    risk = min(risk, MAX_RISK)

    # --- Nivel y resumen ---
    if risk >= RISK_HIGH:
        level = "alto"
        summary = "El sitio presenta múltiples señales de riesgo comercial."
    elif risk >= RISK_MEDIUM:
        level = "medio"
        summary = "Se detectan indicadores que sugieren cautela en la compra."
    else:
        level = "bajo"
        summary = "No se detectan señales relevantes de riesgo comercial."

    return {
        "level": level,
        "score": round(risk, 1),
        "summary": summary,
        "signals": signals[:MAX_SIGNALS],
    }


def analyze(text: str, url: str = "", context: str = "general") -> dict:
    return analyze_commercial_risk(text, url, context)