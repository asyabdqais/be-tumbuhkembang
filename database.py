from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

# ─── Konfigurasi ──────────────────────────────────────────
DATABASE_URL             = os.getenv("DATABASE_URL")
SECRET_KEY               = os.getenv("SECRET_KEY")
ALGORITHM                = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
GEMINI_API_KEY           = os.getenv("GEMINI_API_KEY", "").strip()

# ─── Database Setup ───────────────────────────────────────
engine       = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()
