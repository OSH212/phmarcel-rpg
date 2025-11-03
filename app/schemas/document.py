"""
Document Pydantic schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.enums import DocKind


class DocumentUploadResponse(BaseModel):
    """Schema for document upload response"""
    id: str = Field(..., description="Document UUID")
    intake_id: str
    filename: str
    sha256: str = Field(..., description="SHA256 hash of file content")
    mime_type: str
    size_bytes: int
    uploaded_at: datetime
    doc_kind: DocKind = Field(default=DocKind.UNKNOWN, description="Document classification")
    
    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Schema for full document response with extraction data"""
    id: str = Field(..., description="Document UUID")
    intake_id: str
    filename: str
    sha256: str
    mime_type: str
    size_bytes: int
    stored_path: str
    uploaded_at: datetime
    doc_kind: DocKind
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted structured data")
    is_classified: bool = Field(..., description="True if doc_kind is not unknown")
    is_extracted: bool = Field(..., description="True if extracted_data is not null")
    file_extension: str = Field(..., description="File extension (e.g., .pdf)")
    
    class Config:
        from_attributes = True


class ClassificationResponse(BaseModel):
    """Schema for classification operation response"""
    document_id: str
    doc_kind: DocKind
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Classification confidence score")


class ExtractionResponse(BaseModel):
    """Schema for extraction operation response"""
    document_id: str
    doc_kind: DocKind
    extracted_data: Dict[str, Any]
    fields_extracted: int = Field(..., description="Number of fields successfully extracted")

