import re
from urllib.parse import urlparse

KNOWN_DOMAINS = ["mercadolibre", "amazon", "ebay", "fravega", "garbarino", "carrefour", "coto", "vecompras", "tevecompras"]
HIGH_VALUE_PRODUCTS = ["iphone", "samsung", "macbook", "notebook", "playstation"]
LOGIN_PATTERNS = ["iniciar sesión", "registrate", "crear cuenta", "acceder", "ver precios", "ingresar", "sign in", "log in", "login", "register", "create account"]
PRICE_HIDDEN_PATTERNS = ["ver precio", "consultar precio", "precio no disponible"]
GENERIC_REVIEWS_PATTERNS = [r"\d{3,} reviews", r"\d{3,} opiniones", r"\d{1,3},\d{3}\s*(task\s*)?reviews", r"\d{1,3},\d{3}"]
LEGAL_PATTERNS = ["cuit", "razón social", "direccion", "dirección", "términos", "condiciones", "terms", "privacy policy", "legal"]
SUSPICIOUS_TLDS = [".xyz", ".top", ".click", ".site", ".store", ".online"]
PAYMENT_PRESSURE_PATTERNS = [r"\bdepositá\b", r"\btransferí\b", r"\bcbu\b", r"\bcvu\b", r"\bclave token\b", r"\benviar dinero\b", r"\bpago anticipado\b"]
ECOMMERCE_TEXT_SIGNALS = ["comprar", "carrito", "oferta", "envío", "precio", "descuento", "tienda", "checkout", "pagar", "agregar al carrito", "agregar", "añadir", "stock", "disponible", "buy now", "shop now", "add to cart", "shipping", "price", "discount", "order now", "cart", "buy", "shop", "store"]
ECOMMERCE_URL_SIGNALS = ["shop", "store", "tienda", "compra", "cart", "checkout", "product", "oferta", "catalogo"]

def extract_domain(url: str) -> str:
    try: return urlparse(url).netloc.lower()
    except Exception: return ""

def is_ecommerce_context(text: str, url: str = "") -> bool:
    t = (text or "").lower(); u = (url or "").lower()
    return any(w in t for w in ECOMMERCE_TEXT_SIGNALS) or any(w in u for w in ECOMMERCE_URL_SIGNALS)

def analyze_commercial_risk(text: str, url: str = "") -> dict:
    t = (text or "").lower(); domain = extract_domain(url)
    risk = 0; signals = []
    if not is_ecommerce_context(text, url):
        return {"level": "none", "score": 0, "summary": "", "signals": []}
    if domain and not any(k in domain for k in KNOWN_DOMAINS):
        risk += 4; signals.append("Dominio no reconocido o de baja reputación")
    if domain and any(tld in domain for tld in SUSPICIOUS_TLDS):
        risk += 3; signals.append("TLD asociado a sitios de alto riesgo")
    if any(p in t for p in LOGIN_PATTERNS): risk += 3; signals.append("Acceso restringido o login obligatorio")
    if any(p in t for p in PRICE_HIDDEN_PATTERNS): risk += 2; signals.append("Información de precios no visible")
    if any(p in t for p in HIGH_VALUE_PRODUCTS): risk += 2; signals.append("Producto de alto valor detectado")
    if any(re.search(p, t) for p in GENERIC_REVIEWS_PATTERNS): risk += 3; signals.append("Patrones de reseñas potencialmente artificiales")
    if not any(k in t for k in LEGAL_PATTERNS): risk += 2; signals.append("Ausencia de información legal identificable")
    if any(re.search(p, t) for p in PAYMENT_PRESSURE_PATTERNS): risk += 4; signals.append("Solicitud de transferencia o datos sensibles")
    if domain and any(k in domain for k in KNOWN_DOMAINS): risk *= 0.5
    risk = min(risk, 10)
    level = "alto" if risk >= 7 else "medio" if risk >= 4 else "bajo"
    summary = "El sitio presenta múltiples señales de riesgo comercial." if level == "alto" else "Se detectan indicadores que sugieren cautela en la compra." if level == "medio" else "No se detectan señales relevantes de riesgo comercial."
    return {"level": level, "score": round(risk, 1), "summary": summary, "signals": signals[:5]}

def analyze(text: str, url: str = ""):
    return analyze_commercial_risk(text, url)
