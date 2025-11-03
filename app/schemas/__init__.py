"""
Pydantic schemas for request/response validation
"""
from app.schemas.client import ClientCreate, ClientResponse
from app.schemas.intake import IntakeCreate, IntakeResponse
from app.schemas.document import (
    DocumentResponse,
    DocumentUploadResponse,
    ClassificationResponse,
    ExtractionResponse,
)
from app.schemas.checklist import ChecklistItemResponse, ChecklistResponse

__all__ = [
    "ClientCreate",
    "ClientResponse",
    "IntakeCreate",
    "IntakeResponse",
    "DocumentResponse",
    "DocumentUploadResponse",
    "ClassificationResponse",
    "ExtractionResponse",
    "ChecklistItemResponse",
    "ChecklistResponse",
]
