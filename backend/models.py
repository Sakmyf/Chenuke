"""Modelos SQLAlchemy — Chenuke."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text
from backend.database import Base


# ---------------------------------------------------------------------------
# Helper: timestamp con timezone UTC
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    """datetime.now(UTC) — reemplaza el deprecado datetime.utcnow()."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    plan = Column(String(20), default="free")
    subscription_status = Column(String(20), default="inactive")
    analyses_used = Column(Integer, default=0)
    analyses_limit = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} plan={self.plan!r}>"


# ---------------------------------------------------------------------------
# AnalysisLog
# ---------------------------------------------------------------------------

class AnalysisLog(Base):
    __tablename__ = "analysis_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True)
    analysis_key = Column(String(64), nullable=True, index=True)
    engine_version = Column(String(20))
    level = Column(String(20))
    risk_index = Column(Float)
    response_json = Column(Text, nullable=True)

    # --- Columnas deprecadas (no las usa el engine actual) ---
    trust_score = Column(Float, nullable=True)
    rhetorical_score = Column(Float, nullable=True)
    narrative_score = Column(Float, nullable=True)
    absence_score = Column(Float, nullable=True)
    premium_requested = Column(Boolean, default=False)

    def __repr__(self) -> str:
        return (
            f"<AnalysisLog id={self.id} key={self.analysis_key!r} "
            f"level={self.level!r} v={self.engine_version!r}>"
        )


# ---------------------------------------------------------------------------
# Extension (mejorado)
# ---------------------------------------------------------------------------

class Extension(Base):
    __tablename__ = "extensions"

    id = Column(Integer, primary_key=True, index=True)
    extension_id = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    plan = Column(String(20), default="free")
    pro_token = Column(String(64), nullable=True, unique=True)
    # --- Lemon Squeezy license (activación por el usuario, v15.26) ---
    license_key = Column(String(64), nullable=True, index=True)
    license_instance_id = Column(String(64), nullable=True)
    analyses_used = Column(Integer, default=0)
    analyses_limit = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return f"<Extension id={self.id} ext={self.extension_id!r} plan={self.plan!r}>"