from urllib.parse import urlparse
import re

def _extract_hostname(url: str) -> str:
    raw = url if (url or "").startswith("http") else "https://" + (url or "")
    try: return urlparse(raw.lower()).hostname or ""
    except Exception: return ""

def _detect_source_type(hostname: str) -> str:
    institutional_tlds = [".gov", ".gob", ".gov.ar", ".gob.ar", ".edu", ".edu.ar", ".int", ".org.ar"]
    institutional_exact = ["who.int", "un.org", "unesco.org", "paho.org", "worldbank.org", "imf.org", "chequeado.com", "snopes.com", "factcheck.org", "maldita.es"]
    if any(hostname.endswith(tld) for tld in institutional_tlds): return "institutional"
    if any(hostname == d or hostname.endswith("." + d) for d in institutional_exact): return "institutional"
    social = ["facebook.com", "twitter.com", "x.com", "instagram.com", "tiktok.com", "youtube.com", "t.me", "reddit.com", "threads.net", "whatsapp.com"]
    if any(hostname == d or hostname.endswith("." + d) for d in social): return "social"
    commercial = ["mercadolibre.com", "mercadopago.com", "amazon.com", "amazon.com.br", "amazon.com.mx", "ebay.com", "aliexpress.com", "falabella.com", "fravega.com"]
    if any(hostname == d or hostname.endswith("." + d) for d in commercial): return "commercial"
    suspicious = [".xyz", ".click", ".top", ".tk", ".ml", ".ga", ".cf", ".buzz", ".icu", ".monster"]
    if any(hostname.endswith(tld) for tld in suspicious): return "suspicious"
    shorteners = ["bit.ly", "tinyurl.com", "t.co", "ow.ly", "buff.ly"]
    if any(hostname == s or hostname.endswith("." + s) for s in shorteners): return "suspicious"
    return "unknown"

def _detect_media_signals(text: str) -> bool:
    if not text: return False
    t = text.lower(); signals = 0
    report_verbs = [r"\bdeclaró\b", r"\binformó\b", r"\bsegún\b", r"\breportó\b", r"\bafirmó\b", r"\bseñaló\b", r"\bconfirmó\b", r"\bindicó\b", r"\baseguró\b", r"\bde acuerdo con\b"]
    if sum(1 for p in report_verbs if re.search(p, t)) >= 2: signals += 1
    if re.search(r"\bpor\s+[A-ZÁÉÍÓÚ][a-záéíóú]+\b", text): signals += 1
    if re.search(r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", t): signals += 1
    if re.search(r"\b(política|economía|sociedad|deportes|internacional|cultura|tecnología|salud|judiciales)\b", t): signals += 1
    if text.count('"') >= 2 or text.count('«') >= 1: signals += 1
    return signals >= 3

SOURCE_CONFIG = {
    "institutional": {"trust_level": 0.90, "label": "institutional", "message": "Fuente institucional verificable", "signals": ["fuente institucional verificable"]},
    "media": {"trust_level": 0.65, "label": "media", "message": "Contenido periodístico — puede tener sesgo editorial", "signals": ["medio periodístico detectado"]},
    "commercial": {"trust_level": 0.55, "label": "commercial", "message": "Contenido comercial — orientado a persuadir la compra", "signals": ["contenido comercial — persuasión esperada"]},
    "unknown": {"trust_level": 0.55, "label": "unknown", "message": "Fuente no categorizada — leé con atención", "signals": []},
    "social": {"trust_level": 0.30, "label": "social", "message": "Contenido en red social — sin verificación editorial", "signals": ["red social — sin proceso editorial"]},
    "suspicious": {"trust_level": 0.15, "label": "suspicious", "message": "Dominio de baja confianza — alto escrutinio recomendado", "signals": ["dominio o acortador de baja confianza"]},
}

def analyze_source(url: str, text: str = "") -> dict:
    hostname = _extract_hostname(url) if url else ""
    if not hostname:
        return {"domain": "", "trust_level": 0.55, "type": "unknown", "label": "unknown", "message": "Sin información de fuente", "signals": []}
    source_type = _detect_source_type(hostname)
    if source_type == "unknown" and text and _detect_media_signals(text): source_type = "media"
    cfg = SOURCE_CONFIG[source_type]
    return {"domain": hostname, "trust_level": cfg["trust_level"], "type": source_type, "label": cfg["label"], "message": cfg["message"], "signals": cfg["signals"]}
