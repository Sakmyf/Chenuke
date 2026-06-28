"""Configuración de base de datos — Chenuke."""

from __future__ import annotations

import logging
import os
from typing import Final

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

_DATABASE_URL: str | None = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")

# Pool: tuneable via env vars con defaults razonables
_POOL_SIZE: Final[int] = int(os.getenv("DB_POOL_SIZE", "5"))
_MAX_OVERFLOW: Final[int] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
_POOL_RECYCLE: Final[int] = int(os.getenv("DB_POOL_RECYCLE", "300"))  # 5 min
_POOL_TIMEOUT: Final[int] = int(os.getenv("DB_POOL_TIMEOUT", "30"))

# ---------------------------------------------------------------------------
# Engine (lazy: solo se crea si DATABASE_URL existe)
# ---------------------------------------------------------------------------

_engine = None
SessionLocal = None
Base = declarative_base()


def _build_engine(url: str):
    """Crea el engine de SQLAlchemy con settings seguros para PostgreSQL."""
    kwargs = {
        "pool_pre_ping": True,        # detecta conexiones muertas antes de usarlas
        "pool_size": _POOL_SIZE,
        "max_overflow": _MAX_OVERFLOW,
        "pool_recycle": _POOL_RECYCLE,  # recicla conexiones antes de que PG las cierre
        "pool_timeout": _POOL_TIMEOUT,
    }

    # SQLite no soporta estos parámetros de pool
    if url.startswith("sqlite"):
        kwargs = {"pool_pre_ping": True}

    return create_engine(url, **kwargs)


# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------

if _DATABASE_URL:
    try:
        _engine = _build_engine(_DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        logger.info("Database engine inicializado (pool=%d, overflow=%d, recycle=%ds)",
                     _POOL_SIZE, _MAX_OVERFLOW, _POOL_RECYCLE)
    except Exception as e:
        logger.error("No se pudo crear el engine de base de datos: %s", e)
        _engine = None
        SessionLocal = None
else:
    logger.warning("DATABASE_URL no configurada — la app funciona en modo sin base de datos")


# ---------------------------------------------------------------------------
# FastAPI dependency (para endpoints que usen Depends(get_db))
# ---------------------------------------------------------------------------

def get_db():
    """Generador para FastAPI Depends(). Usa context manager internamente."""
    if SessionLocal is None:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()