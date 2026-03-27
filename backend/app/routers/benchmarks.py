import os
import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.security.rbac import require_roles
from app.services import crypto_service

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


def _bench(fn, *args, data_size: int = 10_000, **kwargs) -> dict:
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    throughput = round((data_size / 1024 / 1024) / (elapsed_ms / 1000), 4) if elapsed_ms > 0 else 0
    return {"time_ms": round(elapsed_ms, 2), "throughput_mbs": throughput}


@router.post("/run")
async def run_benchmarks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    results = []
    sample_data = os.urandom(10_000)  # 10 KB

    # AES-128-GCM
    dek128 = os.urandom(16)
    m = _bench(crypto_service.encrypt_aes_gcm, sample_data, dek128, data_size=10_000)
    results.append({"algorithm": "AES-128-GCM", "operation": "encrypt", "data_size": "10KB",
                    "time_ms": m["time_ms"], "throughput_mbs": m["throughput_mbs"], "category": "Symmetric"})

    # AES-256-GCM
    dek256 = os.urandom(32)
    m = _bench(crypto_service.encrypt_aes_gcm, sample_data, dek256, data_size=10_000)
    results.append({"algorithm": "AES-256-GCM", "operation": "encrypt", "data_size": "10KB",
                    "time_ms": m["time_ms"], "throughput_mbs": m["throughput_mbs"], "category": "Symmetric"})

    # PBKDF2-SHA256 (300K iterations)
    salt = os.urandom(16)
    m = _bench(crypto_service.derive_key, "benchmark_pass", salt, 310000, 32, "sha256", data_size=32)
    results.append({"algorithm": "PBKDF2-SHA256", "operation": "derive_key (310K iter)", "data_size": "32B",
                    "time_ms": m["time_ms"], "throughput_mbs": None, "category": "KDF"})

    # PBKDF2-SHA512 (600K iterations)
    m = _bench(crypto_service.derive_key, "benchmark_pass", salt, 600000, 32, "sha512", data_size=32)
    results.append({"algorithm": "PBKDF2-SHA512", "operation": "derive_key (600K iter)", "data_size": "32B",
                    "time_ms": m["time_ms"], "throughput_mbs": None, "category": "KDF"})

    # ECDSA-P256
    m = _bench(crypto_service.sign_ecdsa, sample_data, data_size=10_000)
    results.append({"algorithm": "ECDSA-P256", "operation": "sign", "data_size": "10KB",
                    "time_ms": m["time_ms"], "throughput_mbs": m["throughput_mbs"], "category": "Asymmetric"})

    # RSA-PSS-2048
    m = _bench(crypto_service.sign_rsa_pss, sample_data, data_size=10_000)
    results.append({"algorithm": "RSA-PSS-2048", "operation": "sign", "data_size": "10KB",
                    "time_ms": m["time_ms"], "throughput_mbs": m["throughput_mbs"], "category": "Asymmetric"})

    # SHA-256
    import hashlib
    m = _bench(lambda: hashlib.sha256(sample_data).hexdigest(), data_size=10_000)
    results.append({"algorithm": "SHA-256", "operation": "hash", "data_size": "10KB",
                    "time_ms": m["time_ms"], "throughput_mbs": m["throughput_mbs"], "category": "Hash"})

    # SHA3-256
    m = _bench(lambda: hashlib.sha3_256(sample_data).hexdigest(), data_size=10_000)
    results.append({"algorithm": "SHA3-256", "operation": "hash", "data_size": "10KB",
                    "time_ms": m["time_ms"], "throughput_mbs": m["throughput_mbs"], "category": "Hash"})

    return {"results": results}


@router.get("/results")
async def benchmark_results(
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    return {"results": [], "message": "Run POST /api/benchmarks/run to generate new results"}
