"""
Checklist Pydantic schemas
"""
from typing import List
from pydantic import BaseModel, Field
from app.models.enums import DocKind, ChecklistStatus, IntakeStatus


class ChecklistItemResponse(BaseModel):
    """Schema for individual checklist item"""
    id: str = Field(..., description="ChecklistItem UUID")
    intake_id: str
    doc_kind: DocKind
    status: ChecklistStatus
    quantity_expected: int = Field(..., description="Number of documents expected")
    quantity_received: int = Field(..., description="Number of documents received")
    is_complete: bool = Field(..., description="True if quantity_received >= quantity_expected")
    progress_percentage: float = Field(..., ge=0.0, le=100.0, description="Completion percentage")
    
    class Config:
        from_attributes = True


class ChecklistResponse(BaseModel):
    """Schema for full checklist with intake status"""
    intake_id: str
    intake_status: IntakeStatus
    is_complete: bool = Field(..., description="True if all checklist items are complete")
    items: List[ChecklistItemResponse] = Field(..., description="List of checklist items")
    total_expected: int = Field(..., description="Total documents expected across all items")
    total_received: int = Field(..., description="Total documents received across all items")
    overall_progress: float = Field(..., ge=0.0, le=100.0, description="Overall completion percentage")

