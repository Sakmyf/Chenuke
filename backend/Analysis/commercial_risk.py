"""commercial_risk — Riesgo comercial, financiero y landings de captación.

Chenuke v15.21

Detecta:
- e-commerce clásico
- landings con formulario
- trading / inversión
- ganancias rápidas
- promesas de ingresos
- porcentajes exagerados
- presión comercial
- ausencia de información legal
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlparse


# ======================================================
# DOMINIOS / TLDS
# ======================================================

KNOWN_DOMAINS: Final[tuple[str, ...]] = (
    "mercadolibre",
    "amazon",
    "ebay",
    "fravega",
    "garbarino",
    "carrefour",
    "coto",
    "vecompras",
    "tevecompras",
    "movistar",
    "personal",
    "claro",
    "aarp",
    "palladiumhotelgroup",
)

LATAM_COMMERCIAL_CCTLDS: Final[tuple[str, ...]] = (
    ".com.ar",
    ".com.mx",
    ".com.co",
    ".com.pe",
    ".com.br",
    ".com.uy",
    ".com.cl",
    ".com.bo",
    ".com.ec",
    ".com.py",
    ".com.gt",
    ".com.sv",
    ".com.hn",
    ".com.ni",
    ".com.cr",
    ".com.pa",
    ".com.do",
)

SUSPICIOUS_TLDS: Final[tuple[str, ...]] = (
    ".xyz",
    ".top",
    ".click",
    ".site",
    ".store",
    ".online",
    ".icu",
    ".buzz",
    ".live",
)


# ======================================================
# E-COMMERCE
# ======================================================

HIGH_VALUE_PRODUCTS: Final[tuple[str, ...]] = (
    "iphone",
    "samsung",
    "macbook",
    "notebook",
    "playstation",
    "crypto",
    "bitcoin",
    "usdt",
)

LOGIN_PATTERNS: Final[tuple[str, ...]] = (
    "iniciar sesión",
    "registrate",
    "regístrate",
    "crear cuenta",
    "acceder",
    "ver precios",
    "ingresar",
    "sign in",
    "log in",
    "login",
    "register",
    "create account",
)

PRICE_HIDDEN_PATTERNS: Final[tuple[str, ...]] = (
    "ver precio",
    "consultar precio",
    "precio no disponible",
)

LEGAL_PATTERNS: Final[tuple[str, ...]] = (
    "cuit",
    "razón social",
    "direccion",
    "dirección",
    "términos",
    "condiciones",
    "terms",
    "privacy policy",
    "política de privacidad",
    "aviso legal",
    "legal",
)

ECOMMERCE_TEXT_SIGNALS: Final[tuple[str, ...]] = (
    "comprar",
    "carrito",
    "oferta",
    "envío",
    "precio",
    "descuento",
    "tienda",
    "checkout",
    "pagar",
    "agregar al carrito",
    "añadir",
    "stock",
    "buy now",
    "shop now",
    "add to cart",
    "shipping",
    "price",
    "discount",
    "order now",
    "buy",
    "shop",
)

ECOMMERCE_URL_SIGNALS: Final[tuple[str, ...]] = (
    "shop",
    "store",
    "tienda",
    "compra",
    "cart",
    "checkout",
    "product",
    "oferta",
    "catalogo",
)


# ======================================================
# FINANZAS / TRADING / GANANCIAS
# ======================================================

FINANCIAL_TEXT_SIGNALS: Final[tuple[str, ...]] = (
    "trading",
    "trader",
    "forex",
    "futuros",
    "opciones",
    "acciones",
    "cripto",
    "criptomonedas",
    "bitcoin",
    "inversión",
    "inversion",
    "invertir",
    "invierta",
    "mercado financiero",
    "mercados reales",
    "ganar dinero",
    "dinero extra",
    "segundo ingreso",
    "ingresos ilimitados",
    "genera ingresos",
    "generar ingresos",
    "desde casa",
    "tareas sencillas",
    "sin experiencia",
    "aprende y gana",
    "aprendé y ganá",
    "aprendé trading",
    "aprende trading",
    "dominar tu mente",
    "no operes solo",
)

FINANCIAL_URL_SIGNALS: Final[tuple[str, ...]] = (
    "trade",
    "trading",
    "trader",
    "forex",
    "crypto",
    "investment",
    "invest",
    "earn",
    "money",
    "ganar",
    "dinero",
    "capital",
)

AGGRESSIVE_CTA_PATTERNS: Final[tuple[str, ...]] = (
    "registrate ahora",
    "regístrate ahora",
    "empezá ahora",
    "empieza ahora",
    "aprenda a negociar",
    "inicia tu camino",
    "sumate",
    "unite ahora",
    "comenzar ahora",
    "registrate",
    "regístrate",
)

FORM_PATTERNS: Final[tuple[str, ...]] = (
    "nombre",
    "apellido",
    "teléfono",
    "telefono",
    "email",
    "correo",
    "tus datos de contacto",
    "acepto la política",
    "formulario",
    "completá",
    "completa",
)


# ======================================================
# REGEX
# ======================================================

_GENERIC_REVIEWS_RE = re.compile(
    r"\d{3,} reviews"
    r"|\d{3,} opiniones"
    r"|\d{1,3},\d{3}\s*(?:task\s*)?reviews"
    r"|\d{1,3},\d{3}",
    re.IGNORECASE,
)

_PAYMENT_PRESSURE_RE = re.compile(
    r"\bdepositá\b"
    r"|\btransferí\b"
    r"|\bcbu\b"
    r"|\bcvu\b"
    r"|\bclave token\b"
    r"|\benviar dinero\b"
    r"|\bpago anticipado\b",
    re.IGNORECASE,
)

ROI_RE = re.compile(
    r"\+\s?\d{2,4}\s?%"
    r"|\b\d{2,4}\s?%\s*(?:de\s*)?(?:ganancia|rentabilidad|retorno|beneficio)",
    re.IGNORECASE,
)

FAST_MONEY_RE = re.compile(
    r"gan[aáe]?\s+dinero\s+(?:rápido|facil|fácil|desde casa)"
    r"|dinero\s+extra\s+(?:rápido|facil|fácil)?"
    r"|segundo\s+ingreso"
    r"|ingresos\s+ilimitados"
    r"|sin\s+experiencia"
    r"|sin\s+entrevista",
    re.IGNORECASE,
)

GUARANTEE_RE = re.compile(
    r"garantizad[oa]s?"
    r"|sin riesgo"
    r"|riesgo cero"
    r"|rentabilidad asegurada"
    r"|ganancias aseguradas"
    r"|resultados asegurados",
    re.IGNORECASE,
)


# ======================================================
# UMBRALES
# ======================================================

MAX_RISK: float = 10.0
RISK_HIGH: float = 7.0
RISK_MEDIUM: float = 4.0
MAX_SIGNALS: int = 6

KNOWN_DOMAIN_FACTOR: float = 0.55
LATAM_CCTLD_FACTOR: float = 0.85
INSTITUTIONAL_FACTOR: float = 0.40


# ======================================================
# HELPERS
# ======================================================

def extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_financial_context(text: str, url: str = "") -> bool:
    t = (text or "").lower()
    u = (url or "").lower()

    return (
        any(w in t for w in FINANCIAL_TEXT_SIGNALS)
        or any(w in u for w in FINANCIAL_URL_SIGNALS)
        or bool(ROI_RE.search(t))
        or bool(FAST_MONEY_RE.search(t))
        or bool(GUARANTEE_RE.search(t))
    )


def is_ecommerce_context(
    text: str,
    url: str = "",
    context: str = "general"
) -> bool:
    t = (text or "").lower()
    u = (url or "").lower()

    url_signal = any(w in u for w in ECOMMERCE_URL_SIGNALS)
    text_signal = any(w in t for w in ECOMMERCE_TEXT_SIGNALS)
    financial_signal = is_financial_context(text, url)

    if context == "institutional":
        return url_signal or bool(_PAYMENT_PRESSURE_RE.search(t))

    return url_signal or text_signal or financial_signal


def _add_signal(signals: list[str], message: str) -> None:
    if message not in signals:
        signals.append(message)


# ======================================================
# MAIN ANALYSIS
# ======================================================

def analyze_commercial_risk(
    text: str,
    url: str = "",
    context: str = "general"
) -> dict:
    t = (text or "").lower()
    domain = extract_domain(url)

    if not is_ecommerce_context(text, url, context):
        return {
            "level": "none",
            "score": 0,
            "summary": "",
            "signals": []
        }

    risk = 0.0
    signals: list[str] = []

    financial = is_financial_context(text, url)

    # ==================================================
    # Dominio / estructura
    # ==================================================

    if domain and any(tld in domain for tld in SUSPICIOUS_TLDS):
        risk += 2.5
        _add_signal(
            signals,
            "Dominio o TLD con mayor riesgo estructural"
        )

    if (
        financial
        and domain
        and not any(k in domain for k in KNOWN_DOMAINS)
        and not any(domain.endswith(tld) for tld in LATAM_COMMERCIAL_CCTLDS)
    ):
        risk += 1.5
        _add_signal(
            signals,
            "Dominio no local asociado a oferta financiera"
        )

    # ==================================================
    # E-commerce clásico
    # ==================================================

    if any(p in t for p in LOGIN_PATTERNS):
        risk += 1.5
        _add_signal(
            signals,
            "Registro o acceso solicitado antes de operar"
        )

    if any(p in t for p in PRICE_HIDDEN_PATTERNS):
        risk += 1.5
        _add_signal(
            signals,
            "Información de precios no visible"
        )

    if any(p in t for p in HIGH_VALUE_PRODUCTS):
        risk += 1.5
        _add_signal(
            signals,
            "Producto o activo de alto valor detectado"
        )

    if _GENERIC_REVIEWS_RE.search(t):
        risk += 2.0
        _add_signal(
            signals,
            "Patrones de reseñas o cifras genéricas detectadas"
        )

    # ==================================================
    # Trading / inversión / ingresos
    # ==================================================

    if financial:
        risk += 3.0
        _add_signal(
            signals,
            "Oferta financiera, trading o ingresos detectada"
        )

    if ROI_RE.search(t):
        risk += 4.0
        _add_signal(
            signals,
            "Promesa de retorno porcentual elevada"
        )

    if FAST_MONEY_RE.search(t):
        risk += 3.0
        _add_signal(
            signals,
            "Promesa de dinero rápido o ingresos fáciles"
        )

    if GUARANTEE_RE.search(t):
        risk += 3.0
        _add_signal(
            signals,
            "Lenguaje de garantía o bajo riesgo financiero"
        )

    if any(p in t for p in AGGRESSIVE_CTA_PATTERNS):
        risk += 1.5
        _add_signal(
            signals,
            "Llamado a la acción comercial agresivo"
        )

    form_hits = sum(
        1
        for p in FORM_PATTERNS
        if p in t
    )

    if form_hits >= 3:
        risk += 2.0
        _add_signal(
            signals,
            "Formulario de captación de datos personales"
        )

    # ==================================================
    # Legales / datos sensibles
    # ==================================================

    if not any(k in t for k in LEGAL_PATTERNS):
        risk += 1.5
        _add_signal(
            signals,
            "Ausencia de información legal identificable"
        )

    if _PAYMENT_PRESSURE_RE.search(t):
        risk += 4.0
        _add_signal(
            signals,
            "Solicitud de transferencia o datos sensibles"
        )

    # ==================================================
    # Descuentos estructurales
    # ==================================================

    if domain and any(k in domain for k in KNOWN_DOMAINS):
        risk *= KNOWN_DOMAIN_FACTOR

    elif domain and any(domain.endswith(tld) for tld in LATAM_COMMERCIAL_CCTLDS):
        risk *= 0.95 if financial else LATAM_CCTLD_FACTOR

    if context == "institutional":
        risk *= INSTITUTIONAL_FACTOR

    risk = min(risk, MAX_RISK)

    # ==================================================
    # Nivel
    # ==================================================

    if risk >= RISK_HIGH:
        level = "alto"
        summary = (
            "El sitio presenta múltiples señales de riesgo comercial o financiero."
        )

    elif risk >= RISK_MEDIUM:
        level = "medio"
        summary = (
            "Se detectan indicadores que sugieren cautela antes de avanzar."
        )

    else:
        level = "bajo"
        summary = (
            "No se detectan señales relevantes de riesgo comercial."
        )

    return {
        "level": level,
        "score": round(risk, 1),
        "summary": summary,
        "signals": signals[:MAX_SIGNALS],
    }


def analyze(text: str, url: str = "", context: str = "general") -> dict:
    return analyze_commercial_risk(text, url, context)