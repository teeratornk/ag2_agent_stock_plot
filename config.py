import os
try:
    import streamlit as st  # existing behavior
except ImportError:
    class _Stub:
        session_state = {}
    st = _Stub()

from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for Azure OpenAI and system settings."""
    
    def __init__(self):
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "").strip()
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        
        # Default model - this is the primary fallback
        self.default_model = os.getenv("AZURE_OPENAI_MODEL", "gpt-4").strip()
        
        # Role specific models with fallback to default_model
        self.model_writer = os.getenv("AZURE_OPENAI_CODE_WRITER", self.default_model).strip()
        self.model_critic = os.getenv("AZURE_OPENAI_CODE_CRITIC", self.default_model).strip()
        self.model_exe = os.getenv("AZURE_OPENAI_CODE_EXE", self.default_model).strip()

    def validate(self):
        missing = [k for k, v in {
            "AZURE_OPENAI_API_KEY": self.api_key,
            "AZURE_OPENAI_API_VERSION": self.api_version,
            "AZURE_OPENAI_ENDPOINT": self.endpoint,
        }.items() if not v]
        if missing:
            return False, f"Missing environment variables: {', '.join(missing)}"
        return True, "Configuration valid"

_env = Config()

# --- LLM CONFIG HELPERS ----------------------------------------------------

def _build_single_entry(model: str, api_key: str | None = None, endpoint: str | None = None) -> Dict[str, Any]:
    api_key = api_key or _env.api_key
    endpoint = (endpoint or _env.endpoint).rstrip("/") if (endpoint or _env.endpoint) else ""
    entry: Dict[str, Any] = {"model": model, "api_key": api_key}

    if endpoint and ("azure" in endpoint.lower() or "cognitiveservices" in endpoint.lower()):
        entry.update({
            "api_type": "azure",
            "azure_endpoint": endpoint,
            "api_version": _env.api_version,
            # In Autogen/AG2 Azure deployment name == model field value
            "azure_deployment": model,
        })
    elif endpoint:
        entry["base_url"] = endpoint
    return entry

def build_llm_config(model: str | None = None) -> Dict[str, Any]:
    """Return generic llm_config (single model) for an agent (works without Streamlit)."""
    sess = getattr(st, "session_state", {})
    chosen = model or sess.get("model", _env.default_model)
    entry = _build_single_entry(chosen)
    return {
        "config_list": [entry],
        "timeout": sess.get("timeout", 60),
        "seed": sess.get("seed", 42),
    }

def build_role_llm_config(role: str) -> Dict[str, Any]:
    role_map = {
        "writer": _env.model_writer,
        "critic": _env.model_critic,
        "exe": _env.model_exe,
    }
    model = role_map.get(role.lower(), _env.default_model)
    return build_llm_config(model)

# --- IMAGE GENERATION CONFIG ------------------------------------------------

def build_image_request_url(kind: str = "generations") -> str:
    """Return full Azure endpoint for image generations or edits."""
    if not _env.endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT not set")
    return f"{_env.endpoint}/openai/deployments/{_env.model_t2i}/images/{kind}?api-version={_env.api_version}"

__all__ = [
    "Config",
    "build_llm_config",
    "build_role_llm_config",
    "build_image_request_url",
]
