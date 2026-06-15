import os, hashlib, time, json, logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)
ENGINE_VERSION = "15.13-clean"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
PRO_TOKEN_SECRET = os.getenv("PRO_TOKEN_SECRET", "")

def rate_limit_key(request: Request) -> str:
    # Detrás de Cloudflare/Railway las IPs se comparten: limitar por extensión.
    return request.headers.get("x-extension-id") or get_remote_address(request)

limiter = Limiter(key_func=rate_limit_key)
app = FastAPI(title="SignalCheck API", version=ENGINE_VERSION)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"], allow_credentials=False, allow_methods=["POST", "GET"], allow_headers=["Content-Type", "x-extension-id", "x-pro-token"])

try:
    from backend.engine import analyze_context
    ENGINE_AVAILABLE = True
except Exception as e:
    logger.warning(f"Engine no disponible: {e}")
    ENGINE_AVAILABLE = False
    def analyze_context(text, url, title="", is_ecommerce=False):
        return {"score": 50, "level": "medio", "message": "Engine no disponible (modo fallback)", "signals": [], "confidence": 0.5, "pro": {}}

try:
    from backend.content_filter import is_explicit_content
except Exception as e:
    logger.warning(f"Filtro de contenido no disponible: {e}")
    def is_explicit_content(url="", title="", text=""):
        return False

try:
    from backend.database import SessionLocal
    from backend.models import AnalysisLog
    DB_AVAILABLE = True
except Exception as e:
    logger.warning(f"Base de datos no disponible: {e}")
    DB_AVAILABLE = False; SessionLocal = None; AnalysisLog = None

class VerifyRequest(BaseModel):
    url: str
    text: str
    title: str = ""
    is_ecommerce: bool = False

def generate_analysis_key(url: str, text: str) -> str:
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    base = f"{url}|{content_hash}|{ENGINE_VERSION}"
    return hashlib.sha256(base.encode()).hexdigest()

def resolve_plan(request: Request) -> str:
    token = request.headers.get("x-pro-token", "")
    return "pro" if PRO_TOKEN_SECRET and token == PRO_TOKEN_SECRET else "free"

def strip_for_plan(response: dict, plan: str) -> dict:
    """Devuelve una copia de la respuesta ajustada al plan. El cálculo nunca cambia; solo la profundidad visible."""
    out = json.loads(json.dumps(response))
    out["meta"]["plan"] = plan
    if plan != "pro":
        out["analysis"]["pro"] = {}
        out["analysis"]["metrics"] = None
    return out

@app.get("/")
def root():
    return {"status": "SignalCheck API running", "version": ENGINE_VERSION, "engine_available": ENGINE_AVAILABLE, "db_available": DB_AVAILABLE}

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": int(time.time()), "engine": ENGINE_AVAILABLE, "database": DB_AVAILABLE}

@app.post("/v3/verify")
@limiter.limit("20/minute")
async def verify(req: VerifyRequest, request: Request):
    if not request.headers.get("x-extension-id"):
        raise HTTPException(status_code=401, detail="Extensión no autorizada")
    if len(req.text) > 20_000:
        raise HTTPException(status_code=400, detail="Texto demasiado largo")

    # --- Privacidad por diseño (ETHICS.md §2.4) ---
    # Contenido sexual explícito: NO se analiza, NO se cachea, NO se loguea la URL.
    # Se devuelve un estado neutral de abstención, sin generar analysis_key.
    if is_explicit_content(req.url, req.title, req.text):
        return {
            "status": "skipped",
            "meta": {"plan": resolve_plan(request), "timestamp": int(time.time()), "cached": False, "skipped_reason": "private_content"},
            "analysis": {
                "structural_index": None,
                "level": "none",
                "message": "Contenido no analizado por privacidad",
                "insight": "SignalCheck no analiza ni registra páginas de contenido privado/adulto.",
                "signals": [], "confidence": None, "pro": {}, "metrics": None,
            },
            "analysis_key": None,
        }

    analysis_key = generate_analysis_key(req.url, req.text)
    plan = resolve_plan(request)

    # --- Cache lookup (se guarda la respuesta COMPLETA; se recorta por plan al leer) ---
    if DB_AVAILABLE and SessionLocal:
        db = SessionLocal()
        try:
            cached = db.query(AnalysisLog).filter(AnalysisLog.analysis_key == analysis_key, AnalysisLog.engine_version == ENGINE_VERSION).first()
            if cached and cached.response_json:
                response = strip_for_plan(json.loads(cached.response_json), plan)
                response["meta"]["cached"] = True
                return response
        except Exception as e:
            logger.warning(f"Cache lookup falló: {e}")
        finally:
            db.close()

    try:
        result = analyze_context(req.text, req.url, req.title, req.is_ecommerce)
        raw_score = result.get("score", 0)
        analysis_data = {
            "structural_index": int(raw_score) if raw_score is not None else None,
            "level": result.get("level", "medio"),
            "message": result.get("message", "Análisis completado"),
            "signals": result.get("signals", []),
            "confidence": (float(result.get("confidence")) if result.get("confidence") is not None else None),
            "insight": result.get("insight", result.get("message", "Análisis completado")),
            "pro": result.get("pro", {}),
            "metrics": (result.get("pro") or {}).get("metrics") or {},
        }
        full_response = {"status": "success", "meta": {"plan": "free", "timestamp": int(time.time()), "cached": False}, "analysis": analysis_data, "analysis_key": analysis_key}

        if DB_AVAILABLE and SessionLocal:
            db = SessionLocal()
            try:
                ri = (analysis_data["structural_index"] / 100) if analysis_data["structural_index"] is not None else None
                log = AnalysisLog(analysis_key=analysis_key, engine_version=ENGINE_VERSION, level=analysis_data["level"], risk_index=ri, response_json=json.dumps(full_response))
                db.add(log); db.commit()
            except Exception as e:
                logger.warning(f"No se pudo guardar en cache: {e}")
            finally:
                db.close()

        return strip_for_plan(full_response, plan)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error en /v3/verify: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")