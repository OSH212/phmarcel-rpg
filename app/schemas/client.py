"""
Client Pydantic schemas
"""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.models.enums import ClientComplexity


class ClientCreate(BaseModel):
    """Schema for creating a new client"""
    name: str = Field(..., min_length=1, max_length=255, description="Client full name")
    email: EmailStr = Field(..., description="Client email address")
    complexity: ClientComplexity = Field(..., description="Client complexity level (simple/average/complex)")


class ClientResponse(BaseModel):
    """Schema for client response"""
    id: str = Field(..., description="Client UUID")
    name: str
    email: str
    complexity: ClientComplexity
    created_at: datetime
    expected_document_count: int = Field(..., description="Total documents expected based on complexity")
    expected_receipt_count: int = Field(..., description="Number of receipts expected")
    
    class Config:
        from_attributes = True

