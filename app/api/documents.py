"""Document classification and extraction API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.document import Document
from app.models.intake import Intake
from app.models.enums import DocKind
from app.schemas.document import ClassificationResponse, ExtractionResponse
from app.schemas.checklist import ChecklistResponse
from app.services.qwen3vl_service import qwen3vl_service
from app.services.checklist_service import update_checklist_for_document, get_checklist_status

router = APIRouter()


@router.post("/{document_id}/classify", response_model=ClassificationResponse)
async def classify_document(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Classify a single document using Qwen3-VL.

    Args:
        document_id: Document UUID
        db: Database session

    Returns:
        ClassificationResponse with doc_kind

    Raises:
        HTTPException 404: If document not found
        HTTPException 500: If classification fails
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document with id {document_id} not found"
        )

    try:
        doc_kind = qwen3vl_service.classify_document(document.stored_path)
        document.doc_kind = DocKind(doc_kind)
        await db.commit()
        await db.refresh(document)

        return ClassificationResponse(
            document_id=document.id,
            doc_kind=document.doc_kind
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )


@router.post("/{document_id}/extract", response_model=ExtractionResponse)
async def extract_document(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Extract fields from a classified document.

    Args:
        document_id: Document UUID
        db: Database session

    Returns:
        ExtractionResponse with extracted data

    Raises:
        HTTPException 404: If document not found
        HTTPException 400: If document not classified or is unknown
        HTTPException 500: If extraction fails
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document with id {document_id} not found"
        )

    if document.doc_kind == DocKind.UNKNOWN:
        raise HTTPException(
            status_code=400,
            detail="Document must be classified before extraction"
        )

    try:
        if document.doc_kind == DocKind.T4:
            extraction = qwen3vl_service.extract_t4(document.stored_path)
        elif document.doc_kind == DocKind.ID:
            extraction = qwen3vl_service.extract_id(document.stored_path)
        elif document.doc_kind == DocKind.RECEIPT:
            extraction = qwen3vl_service.extract_receipt(document.stored_path)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported document kind: {document.doc_kind}"
            )

        document.extracted_data = extraction.model_dump(mode='json')
        await db.commit()
        await db.refresh(document)

        # Update checklist
        await update_checklist_for_document(db, document)

        return ExtractionResponse(
            document_id=document.id,
            doc_kind=document.doc_kind,
            extracted_data=document.extracted_data,
            fields_extracted=len([v for v in document.extracted_data.values() if v is not None])
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}"
        )


