"""
Intake API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.core.config import settings
from app.models.client import Client
from app.models.intake import Intake
from app.models.document import Document
from app.models.checklist_item import ChecklistItem
from app.models.enums import DocKind, ChecklistStatus
from app.schemas.intake import IntakeCreate, IntakeResponse
from app.schemas.document import DocumentUploadResponse, ClassificationResponse, ExtractionResponse
from app.utils.file_handling import save_uploaded_file, calculate_sha256
from app.services.qwen3vl_service import qwen3vl_service
from app.services.checklist_service import update_checklist_for_document

router = APIRouter()


@router.post("", response_model=IntakeResponse, status_code=201)
async def create_intake(
    intake_data: IntakeCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new intake and initialize checklist based on client complexity.

    Checklist initialization:
    - Simple: T4 + ID (2 docs)
    - Average: T4 + ID + 2 receipts (4 docs)
    - Complex: T4 + ID + 5 receipts (8 docs)

    Args:
        intake_data: Intake creation data (client_id, fiscal_year)
        db: Database session

    Returns:
        IntakeResponse with created intake data

    Raises:
        HTTPException 404: If client not found
        HTTPException 409: If intake for this client/fiscal_year already exists
    """
    result = await db.execute(
        select(Client).where(Client.id == intake_data.client_id)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=404,
            detail=f"Client with id {intake_data.client_id} not found"
        )

    result = await db.execute(
        select(Intake).where(
            Intake.client_id == intake_data.client_id,
            Intake.fiscal_year == intake_data.fiscal_year
        )
    )
    existing_intake = result.scalar_one_or_none()

    if existing_intake:
        raise HTTPException(
            status_code=409,
            detail=f"Intake for client {client.name} and fiscal year {intake_data.fiscal_year} already exists"
        )

    new_intake = Intake(
        client_id=intake_data.client_id,
        fiscal_year=intake_data.fiscal_year
    )

    db.add(new_intake)
    await db.flush()
    await db.refresh(new_intake)

    checklist_items = [
        ChecklistItem(
            intake_id=new_intake.id,
            doc_kind=DocKind.T4,
            status=ChecklistStatus.MISSING,
            quantity_expected=1,
            quantity_received=0
        ),
        ChecklistItem(
            intake_id=new_intake.id,
            doc_kind=DocKind.ID,
            status=ChecklistStatus.MISSING,
            quantity_expected=1,
            quantity_received=0
        ),
    ]

    receipt_count = client.expected_receipt_count
    if receipt_count > 0:
        checklist_items.append(
            ChecklistItem(
                intake_id=new_intake.id,
                doc_kind=DocKind.RECEIPT,
                status=ChecklistStatus.MISSING,
                quantity_expected=receipt_count,
                quantity_received=0
            )
        )

    for item in checklist_items:
        db.add(item)

    await db.flush()

    result = await db.execute(
        select(Intake)
        .options(selectinload(Intake.checklist_items))
        .where(Intake.id == new_intake.id)
    )
    intake_with_items = result.scalar_one()

    return intake_with_items


@router.post("/{intake_id}/documents", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    intake_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document to an intake.

    Features:
    - SHA256 hash calculation for duplicate detection
    - File type validation (PDF, PNG, JPG only)
    - File size validation (max 10MB)
    - Duplicate rejection within same intake
    - File storage in /bucket/{intake_id}/ directory

    Args:
        intake_id: Intake UUID
        file: Uploaded file (multipart/form-data)
        db: Database session

    Returns:
        DocumentUploadResponse with document metadata

    Raises:
        HTTPException 400: If file type not allowed
        HTTPException 404: If intake not found
        HTTPException 409: If duplicate file (same SHA256) already exists in this intake
        HTTPException 413: If file size exceeds limit
    """
    result = await db.execute(
        select(Intake).where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()

    if not intake:
        raise HTTPException(
            status_code=404,
            detail=f"Intake with id {intake_id} not found"
        )

    file_content, stored_path, mime_type, file_size = await save_uploaded_file(
        file=file,
        bucket_dir=settings.BUCKET_DIR,
        intake_id=intake_id,
        allowed_extensions=settings.ALLOWED_EXTENSIONS,
        max_file_size=settings.MAX_FILE_SIZE
    )

    sha256_hash = calculate_sha256(file_content)

    result = await db.execute(
        select(Document).where(
            Document.intake_id == intake_id,
            Document.sha256 == sha256_hash
        )
    )
    existing_doc = result.scalar_one_or_none()

    if existing_doc:
        raise HTTPException(
            status_code=409,
            detail=f"Document with hash {sha256_hash} already exists in this intake (filename: {existing_doc.filename})"
        )

    new_document = Document(
        intake_id=intake_id,
        filename=file.filename,
        sha256=sha256_hash,
        mime_type=mime_type,
        size_bytes=file_size,
        stored_path=stored_path,
        doc_kind=DocKind.UNKNOWN
    )

    db.add(new_document)

    try:
        await db.flush()
        await db.refresh(new_document)
    except IntegrityError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate document detected: {str(e)}"
        )

    return new_document


@router.post("/{intake_id}/classify")
async def classify_intake_documents(
    intake_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Classify all unknown documents in an intake."""
    result = await db.execute(
        select(Intake).where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()

    if not intake:
        raise HTTPException(
            status_code=404,
            detail=f"Intake with id {intake_id} not found"
        )

    result = await db.execute(
        select(Document).where(
            Document.intake_id == intake_id,
            Document.doc_kind == DocKind.UNKNOWN
        )
    )
    unknown_docs = result.scalars().all()

    if not unknown_docs:
        raise HTTPException(
            status_code=400,
            detail="No unknown documents to classify in this intake"
        )

    classified = []
    for document in unknown_docs:
        try:
            doc_kind = qwen3vl_service.classify_document(document.stored_path)
            document.doc_kind = DocKind(doc_kind)
            classified.append(ClassificationResponse(
                document_id=document.id,
                doc_kind=document.doc_kind
            ))
        except Exception as e:
            print(f"Failed to classify document {document.id}: {e}")
            continue

    await db.commit()

    return {
        "intake_id": intake_id,
        "total_classified": len(classified),
        "classifications": classified
    }


@router.post("/{intake_id}/extract")
async def extract_intake_documents(
    intake_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Extract fields from all classified documents in an intake."""
    result = await db.execute(
        select(Intake).where(Intake.id == intake_id)
    )
    intake = result.scalar_one_or_none()

    if not intake:
        raise HTTPException(
            status_code=404,
            detail=f"Intake with id {intake_id} not found"
        )

    result = await db.execute(
        select(Document).where(
            Document.intake_id == intake_id,
            Document.doc_kind != DocKind.UNKNOWN
        )
    )
    classified_docs = result.scalars().all()

    if not classified_docs:
        raise HTTPException(
            status_code=400,
            detail="No classified documents to extract in this intake"
        )

    extracted = []
    for document in classified_docs:
        if document.extracted_data:
            continue

        try:
            if document.doc_kind == DocKind.T4:
                extraction = qwen3vl_service.extract_t4(document.stored_path)
            elif document.doc_kind == DocKind.ID:
                extraction = qwen3vl_service.extract_id(document.stored_path)
            elif document.doc_kind == DocKind.RECEIPT:
                extraction = qwen3vl_service.extract_receipt(document.stored_path)
            else:
                continue

            document.extracted_data = extraction.model_dump(mode='json')
            await db.commit()
            await db.refresh(document)

            # Update checklist
            await update_checklist_for_document(db, document)

            extracted.append(ExtractionResponse(
                document_id=document.id,
                doc_kind=document.doc_kind,
                extracted_data=document.extracted_data,
                fields_extracted=len([v for v in document.extracted_data.values() if v is not None])
            ))
        except Exception as e:
            print(f"Failed to extract document {document.id}: {e}")
            continue

    return {
        "intake_id": intake_id,
        "total_extracted": len(extracted),
        "extractions": extracted
    }

