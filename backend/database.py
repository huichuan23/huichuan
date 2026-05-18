"""
数据库连接和模型定义
"""
import os
from sqlalchemy import create_engine, Column, String, Float, Integer, JSON, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local.db")

# Railway 的 PostgreSQL URL 需要把 postgres:// 改成 postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id          = Column(String, primary_key=True)  # 如 uq_E465185_00
    source      = Column(String, index=True)         # uniqlo_ca / hm_ca / zara_ca
    category    = Column(String, index=True)         # top / bottom / shoes / hat / accessory
    name        = Column(String)
    brand       = Column(String, index=True)
    price       = Column(Float)
    currency    = Column(String, default="CAD")
    color       = Column(String)
    color_en    = Column(String)
    color_tone  = Column(String)                     # light / medium / dark
    img         = Column(Text)
    buy         = Column(Text)
    tags        = Column(JSON, default=list)
    avoid_body  = Column(JSON, default=list)
    season      = Column(JSON, default=list)         # spring / summer / fall / winter
    fit         = Column(String, default="regular")  # slim / regular / loose
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    source      = Column(String)
    status      = Column(String)       # running / success / failed
    total       = Column(Integer, default=0)
    message     = Column(Text)
    started_at  = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)


class Feedback(Base):
    __tablename__ = "feedback"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    feedback_type = Column(String, default="general")
    message       = Column(Text, nullable=False)
    contact       = Column(String)
    page          = Column(String)
    user_agent    = Column(Text)
    created_at    = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    email         = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    auth_token    = Column(String, unique=True, index=True)
    profile       = Column(JSON, default=dict)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables are ready")
