import os, hashlib, time, json, logging, asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
ENGINE_VERSION = "15.17-clean"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
PRO_TOKEN_SECRET = os.getenv("PRO_TOKEN_SECRET", "")

# ─── Protección de concurrencia ──────────────────────────────────────────────
# Máximo de análisis corriendo simultáneamente. Cada análisis abre 13 threads
# internos → con 10 concurrentes son 130 threads máximo, manejable en Railway.
# Los requests que superan el límite esperan en cola (no se rechazan).
_ANALYSIS_SEMAPHORE = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_ANALYSES", "10")))

# Lock por analysis_key: evita el "thundering herd" cuando una URL nueva llega
# a 100+ usuarios simultáneos. El primero procesa; los demás esperan el cache.
_key_locks: dict[str, asyncio.Lock] = {}
_key_locks_mutex = asyncio.Lock()

async def _get_key_lock(key: str) -> asyncio.Lock:
    async with _key_locks_mutex:
        if key not in _key_locks:
            _key_locks[key] = asyncio.Lock()
        return _key_locks[key]

# Thread pool dedicado para analyze_context (CPU-bound).
# Evita bloquear el event loop de FastAPI durante el análisis.
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("ANALYSIS_WORKERS", "4")))

def rate_limit_key(request: Request) -> str:
    return request.headers.get("x-extension-id") or get_remote_address(request)

limiter = Limiter(key_func=rate_limit_key)
app = FastAPI(title="SignalCheck API", version=ENGINE_VERSION)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "x-extension-id", "x-pro-token"]
)

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
    out = json.loads(json.dumps(response))
    out["meta"]["plan"] = plan
    if plan != "pro":
        out["analysis"]["pro"] = {}
        out["analysis"]["metrics"] = None
    return out

def _cache_lookup(analysis_key: str):
    """Lee del cache. Retorna el response_json parseado o None."""
    if not (DB_AVAILABLE and SessionLocal):
        return None
    db = SessionLocal()
    try:
        cached = db.query(AnalysisLog).filter(
            AnalysisLog.analysis_key == analysis_key,
            AnalysisLog.engine_version == ENGINE_VERSION
        ).first()
        if cached and cached.response_json:
            return json.loads(cached.response_json)
        return None
    except Exception as e:
        logger.warning(f"Cache lookup falló: {e}")
        return None
    finally:
        db.close()

def _cache_save(analysis_key: str, full_response: dict, level: str, ri):
    """Guarda en cache. Silencia errores — el análisis ya está hecho."""
    if not (DB_AVAILABLE and SessionLocal):
        return
    db = SessionLocal()
    try:
        log = AnalysisLog(
            analysis_key=analysis_key,
            engine_version=ENGINE_VERSION,
            level=level,
            risk_index=ri,
            response_json=json.dumps(full_response)
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning(f"No se pudo guardar en cache: {e}")
    finally:
        db.close()

@app.get("/")
def root():
    return {"status": "SignalCheck API running", "version": ENGINE_VERSION,
            "engine_available": ENGINE_AVAILABLE, "db_available": DB_AVAILABLE}

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": int(time.time()),
            "engine": ENGINE_AVAILABLE, "database": DB_AVAILABLE}

@app.post("/v3/verify")
@limiter.limit("20/minute")
async def verify(req: VerifyRequest, request: Request):
    if not request.headers.get("x-extension-id"):
        raise HTTPException(status_code=401, detail="Extensión no autorizada")
    if len(req.text) > 20_000:
        raise HTTPException(status_code=400, detail="Texto demasiado largo")

    # Privacidad por diseño
    if is_explicit_content(req.url, req.title, req.text):
        return {
            "status": "skipped",
            "meta": {"plan": resolve_plan(request), "timestamp": int(time.time()),
                     "cached": False, "skipped_reason": "private_content"},
            "analysis": {
                "structural_index": None, "level": "none",
                "message": "Contenido no analizado por privacidad",
                "insight": "SignalCheck no analiza ni registra páginas de contenido privado/adulto.",
                "signals": [], "confidence": None, "pro": {}, "metrics": None,
            },
            "analysis_key": None,
        }

    analysis_key = generate_analysis_key(req.url, req.text)
    plan = resolve_plan(request)

    # ── Lock por key: solo UN análisis por URL nueva simultáneamente ──────────
    # Si 500 usuarios piden la misma URL viral al mismo tiempo, el primero
    # la procesa y los otros 499 esperan el lock, leen del cache y retornan.
    key_lock = await _get_key_lock(analysis_key)

    async with key_lock:
        # Re-check cache dentro del lock (puede haber entrado mientras esperaba)
        loop = asyncio.get_event_loop()
        cached = await loop.run_in_executor(_executor, _cache_lookup, analysis_key)
        if cached:
            response = strip_for_plan(cached, plan)
            response["meta"]["cached"] = True
            return response

        # ── Semáforo: máximo N análisis corriendo simultáneamente ─────────────
        async with _ANALYSIS_SEMAPHORE:
            try:
                result = await loop.run_in_executor(
                    _executor,
                    lambda: analyze_context(req.text, req.url, req.title, req.is_ecommerce)
                )
            except Exception as e:
                logger.exception(f"Error en analyze_context: {e}")
                raise HTTPException(status_code=500, detail="Error interno del servidor")

        raw_score = result.get("score", 0)
        analysis_data = {
            "structural_index": int(raw_score) if raw_score is not None else None,
            "level": result.get("level", "medio"),
            "message": result.get("message", "Análisis completado"),
            "signals": result.get("signals", []),
            "confidence": float(result.get("confidence")) if result.get("confidence") is not None else None,
            "insight": result.get("insight", result.get("message", "Análisis completado")),
            "pro": result.get("pro", {}),
            "metrics": (result.get("pro") or {}).get("metrics") or {},
        }
        full_response = {
            "status": "success",
            "meta": {"plan": "free", "timestamp": int(time.time()), "cached": False},
            "analysis": analysis_data,
            "analysis_key": analysis_key
        }

        ri = (analysis_data["structural_index"] / 100) if analysis_data["structural_index"] is not None else None
        await loop.run_in_executor(
            _executor, _cache_save, analysis_key, full_response, analysis_data["level"], ri
        )

        return strip_for_plan(full_response, plan)