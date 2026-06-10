import os, hashlib, time, json, logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)
ENGINE_VERSION = "15.0-clean"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
PRO_TOKEN_SECRET = os.getenv("PRO_TOKEN_SECRET", "")

limiter = Limiter(key_func=get_remote_address)
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
    def analyze_context(text, url, title=""):
        return {"score": 50, "level": "medio", "message": "Engine no disponible (modo fallback)", "signals": [], "confidence": 0.5, "pro": {}}

try:
    from backend.database import get_db
    from backend.models import AnalysisLog
    DB_AVAILABLE = True
except Exception as e:
    logger.warning(f"Base de datos no disponible: {e}")
    DB_AVAILABLE = False; get_db = None; AnalysisLog = None

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

def build_metrics(result: dict, plan: str):
    if plan != "pro": return None
    return (result.get("pro") or {}).get("metrics") or {}

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
    analysis_key = generate_analysis_key(req.url, req.text)
    plan = resolve_plan(request)
    if DB_AVAILABLE and get_db:
        try:
            db = next(get_db())
            cached = db.query(AnalysisLog).filter(AnalysisLog.analysis_key == analysis_key, AnalysisLog.engine_version == ENGINE_VERSION).first()
            if cached and cached.response_json:
                response = json.loads(cached.response_json)
                response["meta"]["plan"] = plan; response["meta"]["cached"] = True
                if plan != "pro": response["analysis"]["pro"] = {}; response["analysis"]["metrics"] = None
                return response
        except Exception as e:
            logger.warning(f"Cache lookup falló: {e}")
    try:
        result = analyze_context(req.text, req.url, req.title)
        analysis_data = {
            "structural_index": int(result.get("score", 0)),
            "level": result.get("level", "medio"),
            "message": result.get("message", "Análisis completado"),
            "signals": result.get("signals", []),
            "confidence": float(result.get("confidence", 0)),
            "insight": result.get("insight", result.get("message", "Análisis completado")),
            "pro": result.get("pro", {}) if plan == "pro" else {},
            "metrics": build_metrics(result, plan),
        }
        response = {"status": "success", "meta": {"plan": plan, "timestamp": int(time.time()), "cached": False}, "analysis": analysis_data, "analysis_key": analysis_key}
        if DB_AVAILABLE and get_db:
            try:
                db = next(get_db())
                response_to_cache = json.loads(json.dumps(response))
                response_to_cache["analysis"]["pro"] = {}; response_to_cache["analysis"]["metrics"] = None; response_to_cache["meta"]["plan"] = "free"
                log = AnalysisLog(analysis_key=analysis_key, engine_version=ENGINE_VERSION, level=analysis_data["level"], risk_index=analysis_data["structural_index"] / 100, response_json=json.dumps(response_to_cache))
                db.add(log); db.commit()
            except Exception as e:
                logger.warning(f"No se pudo guardar en cache: {e}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error en /v3/verify: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
