"""Checklist management service."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.intake import Intake
from app.models.checklist_item import ChecklistItem
from app.models.document import Document


async def update_checklist_for_document(db: AsyncSession, document: Document) -> None:
    """Update checklist when a document is classified and extracted.

    Args:
        db: Database session
        document: Document that was classified/extracted
    """
    if document.doc_kind == "unknown" or not document.extracted_data:
        return

    # Find matching checklist item (regardless of status)
    result = await db.execute(
        select(ChecklistItem).where(
            ChecklistItem.intake_id == document.intake_id,
            ChecklistItem.doc_kind == document.doc_kind
        )
    )
    checklist_item = result.scalar_one_or_none()

    if checklist_item:
        # Count how many documents of this type have been extracted
        result = await db.execute(
            select(Document).where(
                Document.intake_id == document.intake_id,
                Document.doc_kind == document.doc_kind,
                Document.extracted_data != None
            )
        )
        extracted_count = len(result.scalars().all())

        checklist_item.quantity_received = extracted_count
        if checklist_item.quantity_received >= checklist_item.quantity_expected:
            checklist_item.status = "received"
        await db.commit()

        # Check if all items are received
        await check_and_update_intake_status(db, document.intake_id)


async def check_and_update_intake_status(db: AsyncSession, intake_id: str) -> None:
    """Check if all checklist items are received and update intake status.
    
    Args:
        db: Database session
        intake_id: Intake ID to check
    """
    result = await db.execute(
        select(Intake).where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()
    if not intake:
        return

    # Check if all checklist items are received
    result = await db.execute(
        select(ChecklistItem).where(
            ChecklistItem.intake_id == intake_id,
            ChecklistItem.status == "missing"
        )
    )
    missing_items = len(result.scalars().all())

    if missing_items == 0:
        intake.status = "done"
        await db.commit()


async def get_checklist_status(db: AsyncSession, intake_id: str) -> dict:
    """Get checklist status for an intake.
    
    Args:
        db: Database session
        intake_id: Intake ID
        
    Returns:
        Dict with intake info and checklist items
    """
    result = await db.execute(
        select(Intake).where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()
    if not intake:
        return None

    result = await db.execute(
        select(ChecklistItem).where(ChecklistItem.intake_id == intake_id)
    )
    checklist_items = result.scalars().all()
    
    return {
        "intake_id": intake.id,
        "client_id": intake.client_id,
        "fiscal_year": intake.fiscal_year,
        "status": intake.status,
        "checklist": [
            {
                "id": item.id,
                "doc_kind": item.doc_kind,
                "status": item.status
            }
            for item in checklist_items
        ],
        "total_items": len(checklist_items),
        "received_items": sum(1 for item in checklist_items if item.status == "received"),
        "missing_items": sum(1 for item in checklist_items if item.status == "missing")
    }

