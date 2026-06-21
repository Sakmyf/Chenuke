import re
from urllib.parse import urlparse

# Marcas mega-conocidas: solo se usan para un DESCUENTO extra, nunca para
# penalizar a quien no está en la lista. Mantenerla corta y no taxativa es
# intencional — no pretende cubrir el universo de comercio real de LATAM.
KNOWN_DOMAINS = ["mercadolibre", "amazon", "ebay", "fravega", "garbarino", "carrefour", "coto", "vecompras", "tevecompras"]

# ccTLDs comerciales nacionales de LATAM: registrarlos exige trámite legal en
# el país (a menudo con CUIT/RFC/NIT). Es una señal ESTRUCTURAL de legitimidad
# que escala a cualquier comercio real de la región sin necesitar una lista
# de nombres — a diferencia de KNOWN_DOMAINS, esto no requiere mantenimiento.
LATAM_COMMERCIAL_CCTLDS = [
    ".com.ar", ".com.mx", ".com.co", ".com.pe", ".com.br", ".com.uy",
    ".com.cl", ".com.bo", ".com.ec", ".com.py", ".com.gt", ".com.sv",
    ".com.hn", ".com.ni", ".com.cr", ".com.pa", ".com.do",
]

HIGH_VALUE_PRODUCTS = ["iphone", "samsung", "macbook", "notebook", "playstation"]
LOGIN_PATTERNS = ["iniciar sesión", "registrate", "crear cuenta", "acceder", "ver precios", "ingresar", "sign in", "log in", "login", "register", "create account"]
PRICE_HIDDEN_PATTERNS = ["ver precio", "consultar precio", "precio no disponible"]
GENERIC_REVIEWS_PATTERNS = [r"\d{3,} reviews", r"\d{3,} opiniones", r"\d{1,3},\d{3}\s*(task\s*)?reviews", r"\d{1,3},\d{3}"]
LEGAL_PATTERNS = ["cuit", "razón social", "direccion", "dirección", "términos", "condiciones", "terms", "privacy policy", "legal"]
SUSPICIOUS_TLDS = [".xyz", ".top", ".click", ".site", ".store", ".online"]
PAYMENT_PRESSURE_PATTERNS = [r"\bdepositá\b", r"\btransferí\b", r"\bcbu\b", r"\bcvu\b", r"\bclave token\b", r"\benviar dinero\b", r"\bpago anticipado\b"]

# NOTA (v15.15): se quitaron tokens sueltos demasiado genéricos que generaban
# falsos positivos en páginas no comerciales:
#   "disponible"  -> substring de "disponibles" (cupos/turnos/modalidades
#                     disponibles), común en CUALQUIER trámite o portal.
#   "agregar"     -> palabra de uso general; se mantiene la frase específica
#                     "agregar al carrito", que sí es señal real de e-commerce.
#   "cart"        -> substring de "carta", "cartel", "cartón", "cartera".
#   "store"       -> substring de palabras como "restorent" o nombres propios.
ECOMMERCE_TEXT_SIGNALS = ["comprar", "carrito", "oferta", "envío", "precio", "descuento", "tienda", "checkout", "pagar", "agregar al carrito", "añadir", "stock", "buy now", "shop now", "add to cart", "shipping", "price", "discount", "order now", "buy", "shop"]
ECOMMERCE_URL_SIGNALS = ["shop", "store", "tienda", "compra", "cart", "checkout", "product", "oferta", "catalogo"]

_PAYMENT_PRESSURE_RE = re.compile("|".join(PAYMENT_PRESSURE_PATTERNS))


def extract_domain(url: str) -> str:
    try: return urlparse(url).netloc.lower()
    except Exception: return ""


def is_ecommerce_context(text: str, url: str = "", context: str = "general") -> bool:
    t = (text or "").lower(); u = (url or "").lower()
    url_signal = any(w in u for w in ECOMMERCE_URL_SIGNALS)
    text_signal = any(w in t for w in ECOMMERCE_TEXT_SIGNALS)

    if context == "institutional":
        # Las instituciones (.gob.ar, .edu, etc.) no son tiendas: una palabra
        # suelta de uso cotidiano no alcanza para tratarlas como e-commerce.
        # Exigimos una señal de URL explícita de tienda, o presión de pago
        # real (CBU/transferencia) — esto último SIGUE detectando un sitio
        # institucional comprometido/falsificado que pida dinero.
        return url_signal or bool(_PAYMENT_PRESSURE_RE.search(t))

    return url_signal or text_signal


def analyze_commercial_risk(text: str, url: str = "", context: str = "general") -> dict:
    t = (text or "").lower(); domain = extract_domain(url)
    risk = 0; signals = []
    if not is_ecommerce_context(text, url, context):
        return {"level": "none", "score": 0, "summary": "", "signals": []}

    # NOTA (v15.15): se eliminó la penalización "Dominio no reconocido +4".
    # Una whitelist de comercios "conocidos" es inviable para LATAM (miles de
    # pymes legítimas) y penalizaba a cualquier negocio real que no fuera
    # MercadoLibre/Amazon. El riesgo ahora se basa exclusivamente en señales
    # estructurales reales de fraude (TLD basura, login forzado, precio
    # oculto, reviews falsas, ausencia de legales, presión de pago).

    if domain and any(tld in domain for tld in SUSPICIOUS_TLDS):
        risk += 3; signals.append("TLD asociado a sitios de alto riesgo")
    if any(p in t for p in LOGIN_PATTERNS): risk += 3; signals.append("Acceso restringido o login obligatorio")
    if any(p in t for p in PRICE_HIDDEN_PATTERNS): risk += 2; signals.append("Información de precios no visible")
    if any(p in t for p in HIGH_VALUE_PRODUCTS): risk += 2; signals.append("Producto de alto valor detectado")
    if any(re.search(p, t) for p in GENERIC_REVIEWS_PATTERNS): risk += 3; signals.append("Patrones de reseñas potencialmente artificiales")
    if not any(k in t for k in LEGAL_PATTERNS): risk += 2; signals.append("Ausencia de información legal identificable")
    if any(re.search(p, t) for p in PAYMENT_PRESSURE_PATTERNS): risk += 4; signals.append("Solicitud de transferencia o datos sensibles")

    # Descuentos estructurales (nunca penalizaciones): marca mega-reconocida,
    # o ccTLD comercial nacional de LATAM (señal escalable, no requiere lista
    # de nombres — cualquier pyme real con .com.ar/.com.mx/etc. se beneficia).
    if domain and any(k in domain for k in KNOWN_DOMAINS):
        risk *= 0.5
    elif domain and any(domain.endswith(tld) for tld in LATAM_COMMERCIAL_CCTLDS):
        risk *= 0.7

    if context == "institutional":
        risk *= 0.4

    risk = min(risk, 10)
    level = "alto" if risk >= 7 else "medio" if risk >= 4 else "bajo"
    summary = "El sitio presenta múltiples señales de riesgo comercial." if level == "alto" else "Se detectan indicadores que sugieren cautela en la compra." if level == "medio" else "No se detectan señales relevantes de riesgo comercial."
    return {"level": level, "score": round(risk, 1), "summary": summary, "signals": signals[:5]}


def analyze(text: str, url: str = "", context: str = "general"):
    return analyze_commercial_risk(text, url, context)