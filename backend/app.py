import os, hashlib, time, json, logging, asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

ENGINE_VERSION = "15.22-commercial-risk"

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

PRO_TOKEN_SECRET = os.getenv("PRO_TOKEN_SECRET", "")
DEMO_KEY = os.getenv("DEMO_KEY", "")

# ======================================================
# DEV / RATE LIMIT CONFIG
# ======================================================

DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

VERIFY_RATE_LIMIT = os.getenv(
    "VERIFY_RATE_LIMIT",
    "300/minute" if DEV_MODE else "20/minute"
)

DEMO_RATE_LIMIT = os.getenv(
    "DEMO_RATE_LIMIT",
    "60/minute" if DEV_MODE else "5/minute"
)

# ======================================================
# CONCURRENCIA
# ======================================================

_ANALYSIS_SEMAPHORE = asyncio.Semaphore(
    int(os.getenv("MAX_CONCURRENT_ANALYSES", "10"))
)

_key_locks: dict[str, asyncio.Lock] = {}
_key_locks_mutex = asyncio.Lock()

async def _get_key_lock(key: str) -> asyncio.Lock:
    async with _key_locks_mutex:
        if key not in _key_locks:
            _key_locks[key] = asyncio.Lock()
        return _key_locks[key]

_executor = ThreadPoolExecutor(
    max_workers=int(os.getenv("ANALYSIS_WORKERS", "4"))
)

# ======================================================
# RATE LIMIT KEY
# ======================================================

def rate_limit_key(request: Request) -> str:
    return request.headers.get("x-extension-id") or get_remote_address(request)

limiter = Limiter(key_func=rate_limit_key)

# ======================================================
# APP
# ======================================================

app = FastAPI(
    title="Chenuke API",
    version=ENGINE_VERSION
)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=[
        "Content-Type",
        "x-extension-id",
        "x-pro-token",
        "x-demo-key"
    ]
)

# ======================================================
# IMPORT ENGINE
# ======================================================

try:
    from backend.engine import analyze_context
    ENGINE_AVAILABLE = True

except Exception as e:
    logger.warning(f"Engine no disponible: {e}")
    ENGINE_AVAILABLE = False

    def analyze_context(text, url, title=""):
        return {
            "score": 50,
            "level": "yellow",
            "message": "Engine no disponible (modo fallback)",
            "signals": [],
            "confidence": 0.5,
            "pro": {}
        }

# ======================================================
# CONTENT FILTER
# ======================================================

try:
    from backend.content_filter import is_explicit_content

except Exception as e:
    logger.warning(f"Filtro de contenido no disponible: {e}")

    def is_explicit_content(url="", title="", text=""):
        return False

# ======================================================
# DATABASE
# ======================================================

try:
    from backend.database import SessionLocal
    from backend.models import AnalysisLog
    DB_AVAILABLE = True

except Exception as e:
    logger.warning(f"Base de datos no disponible: {e}")
    DB_AVAILABLE = False
    SessionLocal = None
    AnalysisLog = None

# ======================================================
# MODELS
# ======================================================

class VerifyRequest(BaseModel):
    url: str
    text: str
    title: str = ""
    is_ecommerce: bool = False

class DemoRequest(BaseModel):
    text: str

# ======================================================
# HELPERS
# ======================================================

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

def build_response(result: dict, analysis_key: str, plan: str, cached: bool = False):
    raw_score = result.get("score", 0)

    analysis_data = {
        "structural_index": int(raw_score) if raw_score is not None else None,
        "level": result.get("level", "yellow"),
        "message": result.get("message", "Análisis completado"),
        "signals": result.get("signals", []),
        "confidence": float(result.get("confidence")) if result.get("confidence") is not None else None,
        "insight": result.get("insight", result.get("message", "Análisis completado")),
        "pro": result.get("pro", {}),
        "metrics": (result.get("pro") or {}).get("metrics") or {},
    }

    full_response = {
        "status": "success",
        "meta": {
            "plan": plan,
            "timestamp": int(time.time()),
            "cached": cached
        },

        # Compatibilidad nueva
        "score": analysis_data["structural_index"],
        "level": analysis_data["level"],
        "message": analysis_data["message"],
        "signals": analysis_data["signals"],
        "confidence": analysis_data["confidence"],

        # Compatibilidad vieja
        "analysis": analysis_data,

        "analysis_key": analysis_key
    }

    return full_response

# ======================================================
# ROUTES
# ======================================================

@app.get("/")
def root():
    return {
        "status": "Chenuke API running",
        "version": ENGINE_VERSION,
        "engine_available": ENGINE_AVAILABLE,
        "db_available": DB_AVAILABLE,
        "dev_mode": DEV_MODE,
        "verify_rate_limit": VERIFY_RATE_LIMIT
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": int(time.time()),
        "engine": ENGINE_AVAILABLE,
        "database": DB_AVAILABLE,
        "dev_mode": DEV_MODE
    }

@app.post("/v3/verify")
@limiter.limit(VERIFY_RATE_LIMIT)
async def verify(req: VerifyRequest, request: Request):

    if not request.headers.get("x-extension-id"):
        raise HTTPException(
            status_code=401,
            detail="Extensión no autorizada"
        )

    if len(req.text) > 20_000:
        raise HTTPException(
            status_code=400,
            detail="Texto demasiado largo"
        )

    if is_explicit_content(req.url, req.title, req.text):
        return {
            "status": "skipped",
            "meta": {
                "plan": resolve_plan(request),
                "timestamp": int(time.time()),
                "cached": False,
                "skipped_reason": "private_content"
            },
            "score": None,
            "level": "none",
            "message": "Contenido no analizado por privacidad",
            "signals": [],
            "confidence": None,
            "analysis": {
                "structural_index": None,
                "level": "none",
                "message": "Contenido no analizado por privacidad",
                "insight": "Chenuke no analiza ni registra páginas de contenido privado/adulto.",
                "signals": [],
                "confidence": None,
                "pro": {},
                "metrics": None,
            },
            "analysis_key": None,
        }

    analysis_key = generate_analysis_key(req.url, req.text)
    plan = resolve_plan(request)

    key_lock = await _get_key_lock(analysis_key)

    async with key_lock:

        loop = asyncio.get_event_loop()

        cached = await loop.run_in_executor(
            _executor,
            _cache_lookup,
            analysis_key
        )

        if cached:
            response = strip_for_plan(cached, plan)
            response["meta"]["cached"] = True
            return response

        async with _ANALYSIS_SEMAPHORE:

            try:
                # IMPORTANTE:
                # engine.py actual recibe 3 argumentos:
                # text, url, title
                result = await loop.run_in_executor(
                    _executor,
                    lambda: analyze_context(
                        req.text,
                        req.url,
                        req.title
                    )
                )

            except Exception as e:
                logger.exception(f"Error en analyze_context: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Error interno del servidor"
                )

        full_response = build_response(
            result=result,
            analysis_key=analysis_key,
            plan=plan,
            cached=False
        )

        ri = (
            full_response["analysis"]["structural_index"] / 100
            if full_response["analysis"]["structural_index"] is not None
            else None
        )

        await loop.run_in_executor(
            _executor,
            _cache_save,
            analysis_key,
            full_response,
            full_response["analysis"]["level"],
            ri
        )

        return strip_for_plan(full_response, plan)

@app.post("/v3/demo")
@limiter.limit(DEMO_RATE_LIMIT)
async def demo(req: DemoRequest, request: Request):

    demo_key = request.headers.get("x-demo-key", "")

    if not DEMO_KEY or demo_key != DEMO_KEY:
        raise HTTPException(
            status_code=401,
            detail="Demo key inválida"
        )

    text = (req.text or "").strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Texto vacío"
        )

    if len(text) > 1000:
        text = text[:1000]

    analysis_key = generate_analysis_key(
        "demo://web",
        text
    )

    loop = asyncio.get_event_loop()

    key_lock = await _get_key_lock(analysis_key)

    async with key_lock:

        cached = await loop.run_in_executor(
            _executor,
            _cache_lookup,
            analysis_key
        )

        if cached:
            return {
                "status": "success",
                "cached": True,
                "analysis": cached.get("analysis", {})
            }

        async with _ANALYSIS_SEMAPHORE:

            try:
                result = await loop.run_in_executor(
                    _executor,
                    lambda: analyze_context(
                        text,
                        "demo://web",
                        ""
                    )
                )

            except Exception as e:
                logger.exception(f"Error en /v3/demo: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Error interno"
                )

        response = build_response(
            result=result,
            analysis_key=analysis_key,
            plan="free",
            cached=False
        )

        response["analysis"]["signals"] = response["analysis"]["signals"][:3]

        ri = (
            response["analysis"]["structural_index"] / 100
            if response["analysis"]["structural_index"] is not None
            else None
        )

        await loop.run_in_executor(
            _executor,
            _cache_save,
            analysis_key,
            response,
            response["analysis"]["level"],
            ri
        )

        return {
            "status": "success",
            "cached": False,
            "analysis": response["analysis"]
        }