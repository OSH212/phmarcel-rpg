"""
Intake Pydantic schemas
"""
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.models.enums import IntakeStatus


class IntakeCreate(BaseModel):
    """Schema for creating a new intake"""
    client_id: str = Field(..., description="Client UUID")
    fiscal_year: int = Field(..., ge=2000, le=2100, description="Fiscal year (e.g., 2025)")
    
    @field_validator('fiscal_year')
    @classmethod
    def validate_fiscal_year(cls, v: int) -> int:
        if v < 2000 or v > 2100:
            raise ValueError('Fiscal year must be between 2000 and 2100')
        return v


class IntakeResponse(BaseModel):
    """Schema for intake response"""
    id: str = Field(..., description="Intake UUID")
    client_id: str
    fiscal_year: int
    status: IntakeStatus
    created_at: datetime
    is_complete: bool = Field(..., description="True if all checklist items are received")
    
    class Config:
        from_attributes = True

