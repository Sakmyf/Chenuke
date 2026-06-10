from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, Text, ForeignKey
from datetime import datetime
from backend.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    plan = Column(String, default="free")
    subscription_status = Column(String, default="inactive")
    analyses_used = Column(Integer, default=0)
    analyses_limit = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class AnalysisLog(Base):
    __tablename__ = "analysis_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    trust_score = Column(Float)
    rhetorical_score = Column(Float)
    narrative_score = Column(Float)
    absence_score = Column(Float)
    risk_index = Column(Float)
    level = Column(String(20))
    premium_requested = Column(Boolean, default=False)
    engine_version = Column(String(20))
    analysis_key = Column(String(255), nullable=True, index=True)
    response_json = Column(Text, nullable=True)

class Extension(Base):
    __tablename__ = "extensions"
    id = Column(Integer, primary_key=True, index=True)
    extension_id = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    plan = Column(String, default="free")
    analyses_used = Column(Integer, default=0)
    analyses_limit = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
