from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.policy import CryptoPolicy
from app.models.user import User
from app.security.rbac import require_roles

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("")
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(select(CryptoPolicy))
    policies = res.scalars().all()
    return [_to_dict(p) for p in policies]


@router.get("/{level}")
async def get_policy_by_level(
    level: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == level))
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy not found for level: {level}")
    return _to_dict(policy)


@router.put("/{policy_id}")
async def update_policy(
    policy_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    res = await db.execute(select(CryptoPolicy).where(CryptoPolicy.id == policy_id))
    policy = res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    allowed = {"display_name", "kdf_iterations", "signing_required", "require_mfa", "description"}
    update_vals = {k: v for k, v in data.items() if k in allowed}
    if update_vals:
        await db.execute(update(CryptoPolicy).where(CryptoPolicy.id == policy_id).values(**update_vals))
    return {"message": "Policy updated"}


def _to_dict(p: CryptoPolicy) -> dict:
    return {
        "id": p.id,
        "sensitivity_level": p.sensitivity_level,
        "display_name": p.display_name,
        "encryption_algo": p.encryption_algo,
        "key_derivation": p.key_derivation,
        "kdf_iterations": p.kdf_iterations,
        "signing_required": p.signing_required,
        "signing_algo": p.signing_algo,
        "hash_algo": p.hash_algo,
        "min_tls_version": p.min_tls_version,
        "require_mfa": p.require_mfa,
        "description": p.description,
        "created_at": str(p.created_at),
        "updated_at": str(p.updated_at),
    }
