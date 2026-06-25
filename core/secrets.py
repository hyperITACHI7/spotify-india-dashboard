"""
core/secrets.py

Single source of truth for all credentials.
Load order (highest priority first):
  1. Environment variables (set by Docker / CI / shell export)
  2. config/credentials/api_keys.yaml (local development)
  3. Raise a clear, descriptive error if still missing

NO other file in the project may read credentials directly.
All collectors and services must import from this module.
"""
import os
import yaml
from pathlib import Path
from functools import lru_cache
from typing import Any
from dotenv import load_dotenv

# Auto-load the .env file if it exists
env_path = Path(__file__).parent.parent / "config" / "credentials" / ".env"
load_dotenv(env_path)

_CREDS_FILE = Path(__file__).parent.parent / "config" / "credentials" / "api_keys.yaml"

@lru_cache(maxsize=1)
def _load_yaml_credentials() -> dict:
    if not _CREDS_FILE.exists():
        return {}
    with open(_CREDS_FILE, "r") as f:
        return yaml.safe_load(f) or {}

def _get(env_var: str, yaml_path: list[str], required: bool = True) -> str | None:
    """
    Try env var first, then YAML path, then fail loudly.
    """
    # 1. Environment variable
    value = os.environ.get(env_var)
    if value:
        return value

    # 2. YAML file
    data = _load_yaml_credentials()
    for key in yaml_path:
        if not isinstance(data, dict):
            data = None
            break
        data = data.get(key)
    if data:
        return str(data)

    # 3. Fail clearly
    if required:
        raise EnvironmentError(
            f"Missing credential '{env_var}'. "
            f"Set it as an environment variable OR add it to "
            f"config/credentials/api_keys.yaml under {' > '.join(yaml_path)}."
        )
    return None

class DatabaseCredentials:
    host     = property(lambda self: _get("DB_HOST",     ["database", "host"], required=False) or "localhost")
    port     = property(lambda self: int(_get("DB_PORT", ["database", "port"], required=False) or 5432))
    name     = property(lambda self: _get("DB_NAME",     ["database", "name"]))
    user     = property(lambda self: _get("DB_USER",     ["database", "user"]))
    password = property(lambda self: _get("DB_PASSWORD", ["database", "password"]))

class TranslateCredentials:
    api_key = property(lambda self: _get("GOOGLE_TRANSLATE_API_KEY", ["google_translate", "api_key"], required=False))

class LLMCredentials:
    # Reads LLM_API_KEY; falls back to legacy GROQ_API_KEY so existing setups keep working
    @property
    def api_key(self) -> str:
        return (
            os.environ.get("LLM_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or _get("LLM_API_KEY", ["llm", "api_key"])
        )

    @property
    def base_url(self) -> str:
        return (
            os.environ.get("LLM_BASE_URL")
            or "https://api.groq.com/openai/v1"
        )

    @property
    def model(self) -> str:
        return (
            os.environ.get("LLM_MODEL")
            or "llama-3.3-70b-versatile"
        )

# ---- Singleton instances imported by the rest of the codebase ----
database   = DatabaseCredentials()
translate  = TranslateCredentials()
groq_llm   = LLMCredentials()   # legacy alias kept so existing imports don't break
llm        = LLMCredentials()
