"""
Checklist API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.intake import Intake
from app.schemas.checklist import ChecklistResponse, ChecklistItemResponse

router = APIRouter()


@router.get("/{intake_id}/checklist", response_model=ChecklistResponse)
async def get_intake_checklist(
    intake_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get checklist status for an intake.

    Returns all checklist items with their progress, plus overall intake status.

    Args:
        intake_id: Intake UUID
        db: Database session

    Returns:
        ChecklistResponse with all items and overall progress

    Raises:
        HTTPException 404: If intake not found
    """
    result = await db.execute(
        select(Intake)
        .options(selectinload(Intake.checklist_items))
        .where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()

    if not intake:
        raise HTTPException(
            status_code=404,
            detail=f"Intake with id {intake_id} not found"
        )

    items = [
        ChecklistItemResponse(
            id=item.id,
            intake_id=item.intake_id,
            doc_kind=item.doc_kind,
            status=item.status,
            quantity_expected=item.quantity_expected,
            quantity_received=item.quantity_received,
            is_complete=item.quantity_received >= item.quantity_expected,
            progress_percentage=item.progress_percentage
        )
        for item in intake.checklist_items
    ]

    total_expected = sum(item.quantity_expected for item in intake.checklist_items)
    total_received = sum(item.quantity_received for item in intake.checklist_items)
    overall_progress = (total_received / total_expected * 100.0) if total_expected > 0 else 0.0

    return ChecklistResponse(
        intake_id=intake.id,
        intake_status=intake.status,
        is_complete=intake.is_complete,
        items=items,
        total_expected=total_expected,
        total_received=total_received,
        overall_progress=overall_progress
    )

