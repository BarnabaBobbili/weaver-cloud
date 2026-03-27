"""
Azure Key Vault Service — Loads secrets exclusively from Azure Key Vault.

This module provides centralized secret management for the Weaver application.
All secrets (DATABASE_URL, JWT_SECRET_KEY, encryption keys, etc.) are loaded
from Azure Key Vault using Managed Identity authentication.

No .env file fallback — this is a 100% cloud-only deployment.
"""
from __future__ import annotations

import os
import logging
from functools import lru_cache
from typing import Optional

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError

logger = logging.getLogger(__name__)

# Bootstrap config from environment (set by Container Apps)
KEY_VAULT_URL = os.environ.get("KEY_VAULT_URL", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")


class KeyVaultService:
    """
    Service for retrieving secrets from Azure Key Vault.
    
    Uses Managed Identity when running in Azure Container Apps,
    falls back to DefaultAzureCredential for local development with Azure CLI login.
    """
    
    _instance: Optional["KeyVaultService"] = None
    _client: Optional[SecretClient] = None
    _secrets_cache: dict[str, str] = {}
    
    def __new__(cls) -> "KeyVaultService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if self._client is not None:
            return
        
        if not KEY_VAULT_URL:
            raise RuntimeError(
                "KEY_VAULT_URL environment variable is not set. "
                "This application requires Azure Key Vault for secret management."
            )
        
        try:
            # Use Managed Identity if AZURE_CLIENT_ID is set (Container Apps)
            if AZURE_CLIENT_ID:
                credential = ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)
                logger.info(f"Using Managed Identity with client ID: {AZURE_CLIENT_ID[:8]}...")
            else:
                # Fall back to DefaultAzureCredential for local dev (az login)
                credential = DefaultAzureCredential()
                logger.info("Using DefaultAzureCredential (local development mode)")
            
            self._client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
            logger.info(f"Connected to Key Vault: {KEY_VAULT_URL}")
            
        except ClientAuthenticationError as e:
            logger.error(f"Failed to authenticate with Azure Key Vault: {e}")
            raise RuntimeError(
                "Failed to authenticate with Azure Key Vault. "
                "Ensure Managed Identity is configured or run 'az login' locally."
            ) from e
    
    def get_secret(self, name: str, required: bool = True) -> Optional[str]:
        """
        Retrieve a secret from Azure Key Vault.
        
        Args:
            name: Secret name (use hyphens, e.g., 'DATABASE-URL')
            required: If True, raises error when secret is not found
            
        Returns:
            Secret value or None if not found and not required
        """
        # Check cache first
        if name in self._secrets_cache:
            return self._secrets_cache[name]
        
        try:
            secret = self._client.get_secret(name)
            value = secret.value
            self._secrets_cache[name] = value
            logger.debug(f"Retrieved secret: {name}")
            return value
            
        except ResourceNotFoundError:
            if required:
                raise RuntimeError(
                    f"Required secret '{name}' not found in Key Vault. "
                    f"Please add it using: az keyvault secret set --vault-name <vault> --name {name} --value <value>"
                )
            logger.warning(f"Optional secret '{name}' not found in Key Vault")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving secret '{name}': {e}")
            if required:
                raise
            return None
    
    def get_secret_or_default(self, name: str, default: str) -> str:
        """Get a secret or return a default value if not found."""
        value = self.get_secret(name, required=False)
        return value if value is not None else default
    
    def preload_secrets(self, secret_names: list[str]) -> dict[str, str]:
        """
        Preload multiple secrets at once for efficiency.
        
        Args:
            secret_names: List of secret names to load
            
        Returns:
            Dictionary of secret name -> value
        """
        secrets = {}
        for name in secret_names:
            try:
                secrets[name] = self.get_secret(name, required=True)
            except RuntimeError:
                logger.warning(f"Failed to preload secret: {name}")
        return secrets
    
    def clear_cache(self) -> None:
        """Clear the secrets cache (useful for key rotation)."""
        self._secrets_cache.clear()
        logger.info("Cleared secrets cache")


@lru_cache(maxsize=1)
def get_keyvault_service() -> KeyVaultService:
    """Get the singleton KeyVault service instance."""
    return KeyVaultService()


def get_secret(name: str, required: bool = True) -> Optional[str]:
    """Convenience function to get a secret from Key Vault."""
    return get_keyvault_service().get_secret(name, required)


def get_secret_or_default(name: str, default: str) -> str:
    """Convenience function to get a secret with a default fallback."""
    return get_keyvault_service().get_secret_or_default(name, default)
