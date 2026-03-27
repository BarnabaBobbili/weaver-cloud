"""
Azure Blob Storage Service — Upload, download, and manage encrypted file payloads.

This module handles large encrypted file storage in Azure Blob Storage.
Files >1MB are stored in Blob Storage with references in PostgreSQL.
Smaller payloads (<1MB) stay directly in the database.
"""
from __future__ import annotations

import os
import logging
from typing import Optional
from io import BytesIO

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

logger = logging.getLogger(__name__)

# Bootstrap config from environment
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
BLOB_STORAGE_ACCOUNT = os.environ.get("BLOB_STORAGE_ACCOUNT", "weaverstorageprod")


class BlobService:
    """
    Service for managing encrypted payloads in Azure Blob Storage.
    
    Uses Managed Identity for authentication in production,
    falls back to DefaultAzureCredential for local development.
    """
    
    _instance: Optional["BlobService"] = None
    _client: Optional[BlobServiceClient] = None
    
    def __new__(cls) -> "BlobService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if self._client is not None:
            return
        
        try:
            # Use Managed Identity if AZURE_CLIENT_ID is set
            if AZURE_CLIENT_ID:
                credential = ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)
                logger.info("Using Managed Identity for Blob Storage")
            else:
                credential = DefaultAzureCredential()
                logger.info("Using DefaultAzureCredential for Blob Storage")
            
            account_url = f"https://{BLOB_STORAGE_ACCOUNT}.blob.core.windows.net"
            self._client = BlobServiceClient(account_url=account_url, credential=credential)
            logger.info(f"Connected to Blob Storage: {account_url}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Blob Storage client: {e}")
            raise RuntimeError("Failed to connect to Azure Blob Storage") from e
    
    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
        overwrite: bool = False
    ) -> str:
        """
        Upload data to Blob Storage.
        
        Args:
            container_name: Container name (e.g., 'encrypted-payloads')
            blob_name: Blob name (e.g., 'payload_<uuid>.bin')
            data: Raw bytes to upload
            overwrite: If True, overwrite existing blob
            
        Returns:
            Blob URL (e.g., 'https://.../encrypted-payloads/payload_<uuid>.bin')
        """
        try:
            blob_client = self._client.get_blob_client(container=container_name, blob=blob_name)
            blob_client.upload_blob(data, overwrite=overwrite)
            
            blob_url = blob_client.url
            logger.info(f"Uploaded blob: {blob_url} ({len(data)} bytes)")
            return blob_url
            
        except ResourceExistsError:
            logger.error(f"Blob already exists: {container_name}/{blob_name}")
            raise ValueError(f"Blob already exists: {blob_name}")
        except Exception as e:
            logger.error(f"Failed to upload blob: {e}")
            raise RuntimeError(f"Failed to upload blob to Azure Blob Storage") from e
    
    def download_blob(self, container_name: str, blob_name: str) -> bytes:
        """
        Download data from Blob Storage.
        
        Args:
            container_name: Container name
            blob_name: Blob name
            
        Returns:
            Raw bytes from the blob
        """
        try:
            blob_client = self._client.get_blob_client(container=container_name, blob=blob_name)
            blob_data = blob_client.download_blob()
            data = blob_data.readall()
            
            logger.info(f"Downloaded blob: {container_name}/{blob_name} ({len(data)} bytes)")
            return data
            
        except ResourceNotFoundError:
            logger.error(f"Blob not found: {container_name}/{blob_name}")
            raise ValueError(f"Blob not found: {blob_name}")
        except Exception as e:
            logger.error(f"Failed to download blob: {e}")
            raise RuntimeError(f"Failed to download blob from Azure Blob Storage") from e
    
    def download_blob_from_url(self, blob_url: str) -> bytes:
        """
        Download data from Blob Storage using full URL.
        
        Args:
            blob_url: Full blob URL
            
        Returns:
            Raw bytes from the blob
        """
        try:
            # Extract container and blob name from URL
            # Format: https://weaverstorageprod.blob.core.windows.net/encrypted-payloads/payload_xxx.bin
            parts = blob_url.split("/")
            container_name = parts[-2]
            blob_name = parts[-1]
            
            return self.download_blob(container_name, blob_name)
            
        except Exception as e:
            logger.error(f"Failed to parse blob URL: {blob_url}")
            raise ValueError(f"Invalid blob URL format") from e
    
    def delete_blob(self, container_name: str, blob_name: str) -> None:
        """
        Delete a blob from Blob Storage.
        
        Args:
            container_name: Container name
            blob_name: Blob name
        """
        try:
            blob_client = self._client.get_blob_client(container=container_name, blob=blob_name)
            blob_client.delete_blob()
            
            logger.info(f"Deleted blob: {container_name}/{blob_name}")
            
        except ResourceNotFoundError:
            logger.warning(f"Blob not found (already deleted?): {container_name}/{blob_name}")
        except Exception as e:
            logger.error(f"Failed to delete blob: {e}")
            raise RuntimeError(f"Failed to delete blob from Azure Blob Storage") from e
    
    def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """Check if a blob exists in Blob Storage."""
        try:
            blob_client = self._client.get_blob_client(container=container_name, blob=blob_name)
            return blob_client.exists()
        except Exception as e:
            logger.error(f"Failed to check blob existence: {e}")
            return False
    
    def get_blob_url(self, container_name: str, blob_name: str) -> str:
        """Get the full URL for a blob."""
        blob_client = self._client.get_blob_client(container=container_name, blob=blob_name)
        return blob_client.url


# Singleton instance
_blob_service: Optional[BlobService] = None


def get_blob_service() -> BlobService:
    """Get the singleton Blob Storage service instance."""
    global _blob_service
    if _blob_service is None:
        _blob_service = BlobService()
    return _blob_service
