from pydantic_settings import BaseSettings
from supabase import create_client, Client
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    supabase_jwt_secret: str
    frontend_origin: str = "https://vish-karthikeyan.github.io"
    super_admin_email: str = "viswajeethgk@gmail.com"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_supabase_admin() -> Client:
    """Service-role client — bypasses RLS. Backend use only."""
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)
