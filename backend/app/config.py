"""
Weaver Configuration — Azure Cloud-Only Deployment

All secrets are loaded from Azure Key Vault. No .env file fallback.
Bootstrap config (KEY_VAULT_URL, AZURE_CLIENT_ID) comes from Container Apps env vars.
"""
from __future__ import annotations

import os
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


def _normalize_postgres_url(url: str) -> str:
    """Ensure PostgreSQL URL uses asyncpg driver."""
    if not url:
        return url
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings:
    """
    Application settings loaded from Azure Key Vault.
    
    Bootstrap config from environment variables (set by Container Apps):
    - KEY_VAULT_URL: Azure Key Vault URL
    - AZURE_CLIENT_ID: Managed Identity client ID
    - CORS_ORIGINS: Allowed CORS origins
    
    All secrets from Key Vault (secret names use hyphens):
    - DATABASE-URL: PostgreSQL connection string
    - JWT-SECRET-KEY: HS256 signing secret
    - MFA-ENCRYPTION-KEY: Fernet key for TOTP secrets
    - DATA-ENCRYPTION-KEK: AES-256 key for wrapping DEKs
    - BLOB-CONNECTION-STRING: Azure Blob Storage connection
    - SERVICE-BUS-CONNECTION-STRING: Azure Service Bus connection
    - APPINSIGHTS-CONNECTION-STRING: App Insights connection
    """
    
    def __init__(self) -> None:
        # Bootstrap config from environment (set by Container Apps or local testing)
        self.KEY_VAULT_URL: str = os.environ.get("KEY_VAULT_URL", "")
        self.AZURE_CLIENT_ID: str = os.environ.get("AZURE_CLIENT_ID", "")
        
        # App config from environment
        self.APP_NAME: str = "Weaver"
        self.APP_VERSION: str = "1.0.0"
        self.CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
        self.DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
        self.COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
        
        # JWT config (algorithm and expiry are not secrets)
        self.JWT_ALGORITHM: str = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
        self.REFRESH_TOKEN_EXPIRE_DAYS: int = 7
        
        # Security config
        self.PASSWORD_MIN_LENGTH: int = 8
        self.MAX_FAILED_LOGIN_ATTEMPTS: int = 5
        self.LOCKOUT_DURATION_MINUTES: int = 15
        
        # Azure ML config
        self.AZURE_ML_WORKSPACE: str = os.environ.get("AZURE_ML_WORKSPACE", "weaver-ml")
        self.AZURE_ML_MODEL_NAME: str = os.environ.get("AZURE_ML_MODEL_NAME", "sensitivity-classifier")
        self.ML_MODEL_CACHE_PATH: str = "/tmp/ml_model_cache"
        
        # Azure Blob config
        self.BLOB_CONTAINER_PAYLOADS: str = "encrypted-payloads"
        self.BLOB_CONTAINER_MODELS: str = "ml-models"
        self.BLOB_CONTAINER_DATASETS: str = "ml-datasets"
        
        # Threshold for storing in Blob vs DB (1MB)
        self.BLOB_THRESHOLD_BYTES: int = 1024 * 1024
        
        # Secrets cache (loaded lazily from Key Vault)
        self._secrets_loaded: bool = False
        self._database_url: Optional[str] = None
        self._jwt_secret_key: Optional[str] = None
        self._mfa_encryption_key: Optional[str] = None
        self._data_encryption_kek: Optional[str] = None
        self._blob_connection_string: Optional[str] = None
        self._servicebus_connection_string: Optional[str] = None
        self._appinsights_connection_string: Optional[str] = None
    
    def _load_secrets(self) -> None:
        """Load all secrets from Azure Key Vault."""
        if self._secrets_loaded:
            return
        
        from app.services.keyvault_service import get_keyvault_service
        
        kv = get_keyvault_service()
        
        # Required secrets
        self._database_url = _normalize_postgres_url(kv.get_secret("DATABASE-URL", required=True))
        self._jwt_secret_key = kv.get_secret("JWT-SECRET-KEY", required=True)
        self._mfa_encryption_key = kv.get_secret("MFA-ENCRYPTION-KEY", required=True)
        self._data_encryption_kek = kv.get_secret("DATA-ENCRYPTION-KEK", required=True)
        
        # Optional secrets (may not be set up yet)
        self._blob_connection_string = kv.get_secret("BLOB-CONNECTION-STRING", required=False)
        self._servicebus_connection_string = kv.get_secret("SERVICE-BUS-CONNECTION-STRING", required=False)
        self._appinsights_connection_string = kv.get_secret("APPINSIGHTS-CONNECTION-STRING", required=False)
        
        self._secrets_loaded = True
        logger.info("Loaded all secrets from Azure Key Vault")
    
    @property
    def DATABASE_URL(self) -> str:
        self._load_secrets()
        return self._database_url
    
    @property
    def DATABASE_URL_DIRECT(self) -> str:
        """For Azure PostgreSQL, use the same URL (no pooler distinction)."""
        return self.DATABASE_URL
    
    @property
    def JWT_SECRET_KEY(self) -> str:
        self._load_secrets()
        return self._jwt_secret_key
    
    @property
    def MFA_ENCRYPTION_KEY(self) -> str:
        self._load_secrets()
        return self._mfa_encryption_key
    
    @property
    def DATA_ENCRYPTION_KEK(self) -> str:
        self._load_secrets()
        return self._data_encryption_kek
    
    @property
    def BLOB_CONNECTION_STRING(self) -> Optional[str]:
        self._load_secrets()
        return self._blob_connection_string
    
    @property
    def SERVICE_BUS_CONNECTION_STRING(self) -> Optional[str]:
        self._load_secrets()
        return self._servicebus_connection_string
    
    @property
    def APPINSIGHTS_CONNECTION_STRING(self) -> Optional[str]:
        self._load_secrets()
        return self._appinsights_connection_string
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]
    
    # Legacy compatibility - MODEL_PATH no longer used (models come from Azure ML)
    @property
    def MODEL_PATH(self) -> str:
        return f"{self.ML_MODEL_CACHE_PATH}/sensitivity_classifier.joblib"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the singleton Settings instance."""
    return Settings()


# Global settings instance for backward compatibility
settings = get_settings()
