import os
import hashlib
import time
import json
import logging
import asyncio
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from concurrent.futures import ThreadPoolExecutor

# Redis (opcional)
try:
    import redis.asyncio as redis
except ImportError:
    redis = None

# OpenAI / DeepSeek
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ============================================================
# LOGGING ESTRUCTURADO (JSON)
# ============================================================
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        return json.dumps(log_entry)

logger = logging.getLogger("chenuke")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# ============================================================
# CONFIG
# ============================================================
ENGINE_VERSION = "15.24-pro-full"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
PRO_TOKEN_SECRET = os.getenv("PRO_TOKEN_SECRET", "")
DEMO_KEY = os.getenv("DEMO_KEY", "")
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

# Caché
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 hora
REDIS_URL = os.getenv("REDIS_URL", None)  # opcional

# Concurrencia
MAX_CONCURRENT_ANALYSES = int(os.getenv("MAX_CONCURRENT_ANALYSES", "10"))
ANALYSIS_WORKERS = int(os.getenv("ANALYSIS_WORKERS", "2"))
ENGINE_TIMEOUT = int(os.getenv("ENGINE_TIMEOUT", "30"))  # segundos

# Rate limits
VERIFY_RATE_LIMIT = os.getenv("VERIFY_RATE_LIMIT", "60/minute" if DEV_MODE else "60/minute")
DEMO_RATE_LIMIT = os.getenv("DEMO_RATE_LIMIT", "60/minute" if DEV_MODE else "5/minute")

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_CLIENT = None
_CHAT_CACHE: Dict[str, Dict] = {}
_CHAT_CACHE_TTL = 3600  # 1 hora

if DEEPSEEK_API_KEY and OpenAI:
    try:
        DEEPSEEK_CLIENT = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )
        logger.info("Cliente DeepSeek inicializado correctamente")
    except Exception as e:
        logger.error(f"Error inicializando DeepSeek: {e}")
        DEEPSEEK_CLIENT = None
else:
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY no configurada. El endpoint /v3/chat-analysis no estará disponible.")
    if not OpenAI:
        logger.warning("Librería openai no instalada. El endpoint /v3/chat-analysis no estará disponible.")

# ============================================================
# REDIS (opcional)
# ============================================================
redis_client: Optional[redis.Redis] = None

async def init_redis():
    global redis_client
    if REDIS_URL and redis:
        try:
            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            await redis_client.ping()
            logger.info("Redis conectado correctamente", extra={"extra": {"redis_url": REDIS_URL}})
        except Exception as e:
            logger.warning(f"Redis no disponible: {e}", extra={"extra": {"error": str(e)}})
            redis_client = None
    else:
        logger.info("Redis no configurado, usando caché local y DB")

# ============================================================
# ENGINE Y DEPENDENCIAS
# ============================================================
try:
    from backend.engine import analyze_context
    ENGINE_AVAILABLE = True
except Exception as e:
    logger.warning(f"Engine no disponible: {e}")
    ENGINE_AVAILABLE = False
    def analyze_context(text, url, title=""):
        return {"score": 50, "level": "yellow", "message": "Engine no disponible (fallback)", "signals": [], "confidence": 0.5, "pro": {}}

try:
    from backend.content_filter import is_explicit_content
except Exception:
    def is_explicit_content(url="", title="", text=""):
        return False

try:
    from backend.database import SessionLocal
    from backend.models import AnalysisLog
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False
    SessionLocal = None
    AnalysisLog = None

# ============================================================
# CACHÉ LOCAL (LRU en memoria)
# ============================================================
_local_cache: Dict[str, Dict[str, Any]] = {}
_local_cache_lock = asyncio.Lock()

async def get_local_cache(key: str) -> Optional[Dict]:
    async with _local_cache_lock:
        entry = _local_cache.get(key)
        if entry and time.time() - entry["timestamp"] < 300:  # 5 min TTL
            return entry["data"]
        elif entry:
            del _local_cache[key]
        return None

async def set_local_cache(key: str, data: Dict):
    async with _local_cache_lock:
        _local_cache[key] = {"timestamp": time.time(), "data": data}

# ============================================================
# CACHÉ CON REDIS
# ============================================================
async def get_redis_cache(key: str) -> Optional[Dict]:
    if redis_client:
        try:
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
    return None

async def set_redis_cache(key: str, data: Dict, ttl: int = CACHE_TTL):
    if redis_client:
        try:
            await redis_client.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

# ============================================================
# CACHÉ EN BASE DE DATOS (existente)
# ============================================================
def _cache_lookup_db(analysis_key: str):
    if not DB_AVAILABLE:
        return None
    db = SessionLocal()
    try:
        cached = db.query(AnalysisLog).filter(
            AnalysisLog.analysis_key == analysis_key,
            AnalysisLog.engine_version == ENGINE_VERSION
        ).first()
        if cached and cached.response_json:
            return json.loads(cached.response_json)
    except Exception as e:
        logger.warning(f"DB cache lookup failed: {e}")
    finally:
        db.close()
    return None

def _cache_save_db(analysis_key: str, full_response: dict, level: str, ri):
    if not DB_AVAILABLE:
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
        logger.warning(f"DB cache save failed: {e}")
    finally:
        db.close()

# ============================================================
# MÉTRICAS BÁSICAS
# ============================================================
_metrics = {
    "requests_total": 0,
    "requests_by_plan": {"free": 0, "pro": 0},
    "cache_hits": 0,
    "cache_misses": 0,
    "avg_response_time": 0.0,
    "last_100_times": [],
}

def update_metrics(plan: str, cached: bool, duration: float):
    _metrics["requests_total"] += 1
    _metrics["requests_by_plan"][plan] = _metrics["requests_by_plan"].get(plan, 0) + 1
    if cached:
        _metrics["cache_hits"] += 1
    else:
        _metrics["cache_misses"] += 1
    _metrics["last_100_times"].append(duration)
    if len(_metrics["last_100_times"]) > 100:
        _metrics["last_100_times"].pop(0)
    _metrics["avg_response_time"] = sum(_metrics["last_100_times"]) / len(_metrics["last_100_times"])

# ============================================================
# APP
# ============================================================
app = FastAPI(title="Chenuke API", version=ENGINE_VERSION)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "x-extension-id", "x-pro-token", "x-demo-key"]
)

# Semáforo y executor
_analysis_semaphore = asyncio.Semaphore(MAX_CONCURRENT_ANALYSES)
_executor = ThreadPoolExecutor(max_workers=ANALYSIS_WORKERS)
_key_locks: Dict[str, asyncio.Lock] = {}
_key_locks_mutex = asyncio.Lock()

# ============================================================
# LIFECYCLE
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_redis()
    logger.info("Chenuke API iniciada", extra={"extra": {"version": ENGINE_VERSION, "dev_mode": DEV_MODE}})
    yield
    # Shutdown
    if redis_client:
        await redis_client.close()
    _executor.shutdown(wait=True)
    logger.info("Chenuke API cerrada")

app.router.lifespan_context = lifespan

# ============================================================
# HELPERS
# ============================================================
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
    return {
        "status": "success",
        "meta": {"plan": plan, "timestamp": int(time.time()), "cached": cached},
        "score": analysis_data["structural_index"],
        "level": analysis_data["level"],
        "message": analysis_data["message"],
        "signals": analysis_data["signals"],
        "confidence": analysis_data["confidence"],
        "analysis": analysis_data,
        "analysis_key": analysis_key
    }

async def get_cached_result(analysis_key: str) -> Optional[Dict]:
    # 1. Memoria local
    cached = await get_local_cache(analysis_key)
    if cached:
        return cached
    # 2. Redis
    cached = await get_redis_cache(analysis_key)
    if cached:
        await set_local_cache(analysis_key, cached)
        return cached
    # 3. Base de datos
    loop = asyncio.get_event_loop()
    cached = await loop.run_in_executor(_executor, _cache_lookup_db, analysis_key)
    if cached:
        await set_redis_cache(analysis_key, cached)
        await set_local_cache(analysis_key, cached)
        return cached
    return None

async def save_cached_result(analysis_key: str, data: Dict, level: str, ri):
    await set_local_cache(analysis_key, data)
    await set_redis_cache(analysis_key, data)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, _cache_save_db, analysis_key, data, level, ri)

# ============================================================
# MODELS
# ============================================================
class VerifyRequest(BaseModel):
    url: str
    text: str
    title: str = ""
    is_ecommerce: bool = False

class DemoRequest(BaseModel):
    text: str

class ChatAnalysisRequest(BaseModel):
    text: str
    title: str = ""
    url: str = ""
    heuristic: dict = {}

# ============================================================
# ROUTES
# ============================================================
@app.get("/")
def root():
    return {
        "status": "Chenuke API running",
        "version": ENGINE_VERSION,
        "engine_available": ENGINE_AVAILABLE,
        "db_available": DB_AVAILABLE,
        "redis_available": redis_client is not None,
        "dev_mode": DEV_MODE,
    }

@app.get("/health")
async def health():
    redis_status = "ok" if redis_client is not None else "not_configured"
    if redis_client:
        try:
            await redis_client.ping()
        except:
            redis_status = "error"
    db_status = "ok" if DB_AVAILABLE else "error"
    if DB_AVAILABLE:
        try:
            db = SessionLocal()
            db.execute("SELECT 1")
            db.close()
        except:
            db_status = "error"
    return {
        "status": "ok",
        "timestamp": int(time.time()),
        "engine": ENGINE_AVAILABLE,
        "database": db_status,
        "redis": redis_status,
        "dev_mode": DEV_MODE,
        "version": ENGINE_VERSION,
        "metrics": {
            "requests_total": _metrics["requests_total"],
            "cache_hits": _metrics["cache_hits"],
            "cache_misses": _metrics["cache_misses"],
            "avg_response_time_ms": round(_metrics["avg_response_time"] * 1000, 2),
            "requests_by_plan": _metrics["requests_by_plan"],
        }
    }

@app.post("/v3/verify")
@limiter.limit(VERIFY_RATE_LIMIT)
async def verify(req: VerifyRequest, request: Request):
    start_time = time.time()
    plan = resolve_plan(request)

    if not request.headers.get("x-extension-id"):
        raise HTTPException(status_code=401, detail="Extensión no autorizada")
    if len(req.text) > 20_000:
        raise HTTPException(status_code=400, detail="Texto demasiado largo")

    if is_explicit_content(req.url, req.title, req.text):
        return {
            "status": "skipped",
            "meta": {"plan": plan, "timestamp": int(time.time()), "cached": False, "skipped_reason": "private_content"},
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

    async with _key_locks_mutex:
        if analysis_key not in _key_locks:
            _key_locks[analysis_key] = asyncio.Lock()
    key_lock = _key_locks[analysis_key]

    async with key_lock:
        cached = await get_cached_result(analysis_key)
        if cached:
            response = strip_for_plan(cached, plan)
            response["meta"]["cached"] = True
            duration = time.time() - start_time
            update_metrics(plan, True, duration)
            logger.info("Análisis cacheado (verify)", extra={"extra": {
                "plan": plan,
                "analysis_key": analysis_key,
                "duration_ms": round(duration*1000, 2),
                "level": response.get("level"),
                "score": response.get("score"),
                "cached": True,
                "ip": request.client.host if request.client else None
            }})
            return response

        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    _executor,
                    lambda: analyze_context(req.text, req.url, req.title)
                ),
                timeout=ENGINE_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error("Engine timeout", extra={"extra": {"analysis_key": analysis_key}})
            raise HTTPException(status_code=504, detail="Engine timeout")
        except Exception as e:
            logger.exception("Error en analyze_context", extra={"extra": {"analysis_key": analysis_key}})
            raise HTTPException(status_code=500, detail="Error interno del servidor")

        full_response = build_response(result, analysis_key, plan, cached=False)
        ri = (full_response["analysis"]["structural_index"] / 100
              if full_response["analysis"]["structural_index"] is not None else None)

        asyncio.create_task(save_cached_result(analysis_key, full_response, full_response["analysis"]["level"], ri))

        response = strip_for_plan(full_response, plan)
        duration = time.time() - start_time
        update_metrics(plan, False, duration)
        logger.info("Análisis completado (verify)", extra={"extra": {
            "plan": plan,
            "analysis_key": analysis_key,
            "duration_ms": round(duration*1000, 2),
            "level": response.get("level"),
            "score": response.get("score"),
            "cached": False,
            "ip": request.client.host if request.client else None
        }})
        return response

@app.post("/v3/demo")
@limiter.limit(DEMO_RATE_LIMIT)
async def demo(req: DemoRequest, request: Request):
    start_time = time.time()
    demo_key = request.headers.get("x-demo-key", "")
    if not DEMO_KEY or demo_key != DEMO_KEY:
        raise HTTPException(status_code=401, detail="Demo key inválida")

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vacío")
    if len(text) > 1000:
        text = text[:1000]

    analysis_key = generate_analysis_key("demo://web", text)

    async with _key_locks_mutex:
        if analysis_key not in _key_locks:
            _key_locks[analysis_key] = asyncio.Lock()
    key_lock = _key_locks[analysis_key]

    async with key_lock:
        cached = await get_cached_result(analysis_key)
        if cached:
            response_data = cached.get("analysis", {})
            duration = time.time() - start_time
            update_metrics("free", True, duration)
            logger.info("Análisis cacheado (demo)", extra={"extra": {
                "analysis_key": analysis_key,
                "duration_ms": round(duration*1000, 2),
                "cached": True,
                "ip": request.client.host if request.client else None
            }})
            return {"status": "success", "cached": True, "analysis": response_data}

        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    _executor,
                    lambda: analyze_context(text, "demo://web", "")
                ),
                timeout=ENGINE_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error("Engine timeout (demo)", extra={"extra": {"analysis_key": analysis_key}})
            raise HTTPException(status_code=504, detail="Engine timeout")
        except Exception as e:
            logger.exception("Error en /v3/demo", extra={"extra": {"analysis_key": analysis_key}})
            raise HTTPException(status_code=500, detail="Error interno")

        response = build_response(result, analysis_key, "free", cached=False)
        response["analysis"]["signals"] = response["analysis"]["signals"][:3]

        ri = (response["analysis"]["structural_index"] / 100
              if response["analysis"]["structural_index"] is not None else None)

        asyncio.create_task(save_cached_result(analysis_key, response, response["analysis"]["level"], ri))

        duration = time.time() - start_time
        update_metrics("free", False, duration)
        logger.info("Análisis completado (demo)", extra={"extra": {
            "analysis_key": analysis_key,
            "duration_ms": round(duration*1000, 2),
            "level": response["analysis"]["level"],
            "score": response["analysis"]["structural_index"],
            "cached": False,
            "ip": request.client.host if request.client else None
        }})
        return {"status": "success", "cached": False, "analysis": response["analysis"]}

# ============================================================
# NUEVO ENDPOINT: /v3/chat-analysis (DeepSeek)
# ============================================================
@app.post("/v3/chat-analysis")
@limiter.limit("10/minute")
async def chat_analysis(req: ChatAnalysisRequest, request: Request):
    """
    Endpoint exclusivo para PRO/PREMIUM.
    Genera un informe en lenguaje natural usando DeepSeek.
    """
    # 1. Verificar plan
    plan = resolve_plan(request)
    if plan not in ("pro", "premium"):
        raise HTTPException(
            status_code=403,
            detail="Esta función requiere una suscripción PRO o PREMIUM"
        )

    # 2. Validar texto
    text = (req.text or "").strip()
    if len(text) < 80:
        raise HTTPException(400, "Texto insuficiente (mínimo 80 caracteres)")

    # 3. Verificar que DeepSeek esté disponible
    if DEEPSEEK_CLIENT is None:
        logger.error("DeepSeek no disponible")
        raise HTTPException(503, "El servicio de inteligencia artificial no está disponible")

    # 4. Generar clave de caché
    cache_key = hashlib.sha256((text + plan + req.title).encode()).hexdigest()
    if cache_key in _CHAT_CACHE:
        entry = _CHAT_CACHE[cache_key]
        if time.time() - entry["timestamp"] < _CHAT_CACHE_TTL:
            logger.info(f"Informe IA devuelto desde caché (plan {plan})")
            return entry["data"]
        else:
            del _CHAT_CACHE[cache_key]

    # 5. Elegir modelo según plan
    model = "deepseek-v4-pro" if plan == "premium" else "deepseek-v4-flash"
    logger.info(f"Generando informe con {model} para plan {plan}")

    # 6. Construir prompt
    heuristic_summary = ""
    if req.heuristic:
        score = req.heuristic.get("score", "N/A")
        level = req.heuristic.get("level", "desconocido")
        signals = req.heuristic.get("signals", [])
        signals_text = "\n".join([f"- {s.get('label', '')}: {s.get('detail', '')}" for s in signals[:5]])
        heuristic_summary = f"""
        El motor heurístico de Chenuke detectó:
        - Score: {score}/100
        - Nivel de riesgo: {level}
        - Señales principales:
        {signals_text}
        """

    prompt = f"""
Eres Chenuke, un analista experto en manipulación narrativa y comunicación digital.
Tu misión es ayudar a las personas a tomar decisiones informadas analizando textos sospechosos.

Analiza el siguiente texto y genera un informe en lenguaje claro, directo y útil.

**Estructura del informe:**

1. **📌 Resumen ejecutivo** (1 párrafo, 2-3 líneas):
   - ¿El texto presenta señales de manipulación?
   - ¿Qué debería hacer el lector?

2. **🚨 Señales detectadas** (lista de viñetas):
   - Cada señal debe incluir: qué técnica se usó y una cita textual breve como ejemplo.
   - Ejemplo: "Presión de urgencia: 'Última oportunidad, solo hoy'"

3. **💡 Recomendación concreta**:
   - ¿El lector debería confiar, dudar o investigar más?
   - ¿Qué acción específica debería tomar?

4. **🎯 Sugerencia de mejora** (solo si es una landing de ventas o promoción):
   - 3 formas concretas de hacer el texto menos manipulativo y más ético.

**Texto a analizar:**
---
{text[:3000]}
---

{heuristic_summary}

**Instrucciones adicionales:**
- Usá un tono profesional pero accesible (como un asesor de confianza).
- No uses jerga técnica innecesaria.
- Sé objetivo: no juzgues el contenido, solo exponé su estructura.
- Si no hay señales claras de manipulación, decilo honestamente.

¡Generá el informe ahora!
"""

    # 7. Llamar a DeepSeek con timeout
    try:
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                _executor,
                lambda: DEEPSEEK_CLIENT.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "Eres un analista experto en manipulación narrativa y comunicación digital."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=800 if plan == "pro" else 1200,
                )
            ),
            timeout=30.0
        )

        report_text = response.choices[0].message.content

        # 8. Registrar uso
        logger.info(f"Informe generado para plan {plan}, modelo {model}, tokens: {response.usage.total_tokens}")

        response_data = {
            "status": "success",
            "plan": plan,
            "model": model,
            "report": report_text,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

        # Guardar en caché
        _CHAT_CACHE[cache_key] = {
            "timestamp": time.time(),
            "data": response_data
        }

        return response_data

    except asyncio.TimeoutError:
        logger.error(f"Timeout generando informe con {model}")
        raise HTTPException(504, "El servicio de inteligencia artificial no respondió a tiempo")
    except Exception as e:
        logger.exception(f"Error en /v3/chat-analysis: {e}")
        raise HTTPException(500, "Error generando el informe. Intentá de nuevo en unos segundos.")