import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL    = os.getenv("DATABASE_URL", "postgresql://automais:automais@db:5432/automais")
    JWT_SECRET      = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_EXPIRY_HOURS= int(os.getenv("JWT_EXPIRY_HOURS", 24))
    SUPABASE_URL    = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    
    # Permitir o Vercel (produção) e localhost (desenvolvimento)
    CORS_ORIGINS    = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173,https://automais-one.vercel.app,https://automais.vercel.app").split(",")
    DEBUG           = os.getenv("FLASK_ENV") == "development"
