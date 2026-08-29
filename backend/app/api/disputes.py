from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.app.database import get_db
from backend.app.models.dispute import Dispute

router = APIRouter(prefix="/api/disputes", tags=["Disputes"])

@router.get("")
async def list_disputes(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves internal disputes with optional status filtering.
    """
    stmt = select(Dispute).order_by(Dispute.created_at.desc()).offset(offset).limit(limit)
    if status_filter:
        stmt = stmt.where(Dispute.status == status_filter)
        
    result = await db.execute(stmt)
    disputes = result.scalars().all()
    return disputes

@router.get("/{dispute_id}")
async def get_dispute_detail(
    dispute_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches full dispute details including attached evidence documents and policy evaluation results.
    """
    stmt = (
        select(Dispute)
        .options(
            selectinload(Dispute.documents),
            selectinload(Dispute.policy_results)
        )
        .where(Dispute.id == dispute_id)
    )
    result = await db.execute(stmt)
    dispute = result.scalar_one_or_none()
    
    if not dispute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispute with ID {dispute_id} not found"
        )
    return dispute
