"""
ChecklistItem database model
"""
import uuid
from sqlalchemy import Column, Integer, Enum, ForeignKey, String
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import DocKind, ChecklistStatus


class ChecklistItem(Base):
    """
    ChecklistItem model tracking required documents for an intake.
    
    Features:
    - Tracks expected vs received document counts (important for receipts)
    - Auto-initialized based on client complexity when intake is created
    - Status transitions: missing → received (when document is extracted)
    
    Example for complex client:
    - 1 T4 (quantity_expected=1, quantity_received=0)
    - 1 ID (quantity_expected=1, quantity_received=0)
    - 5 receipts (quantity_expected=5, quantity_received=0)
    """
    __tablename__ = "checklist_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    intake_id = Column(String(36), ForeignKey("intakes.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_kind = Column(Enum(DocKind), nullable=False)  # T4, receipt, or id (not unknown)
    status = Column(Enum(ChecklistStatus), default=ChecklistStatus.MISSING, nullable=False)
    quantity_expected = Column(Integer, default=1, nullable=False)  # Expected count (1 for T4/ID, 2 or 5 for receipts)
    quantity_received = Column(Integer, default=0, nullable=False)  # Actual count received

    # Relationships
    intake = relationship("Intake", back_populates="checklist_items")

    def __repr__(self):
        return f"<ChecklistItem(id={self.id}, doc_kind={self.doc_kind.value}, status={self.status.value}, {self.quantity_received}/{self.quantity_expected})>"

    @property
    def is_complete(self) -> bool:
        """Check if required quantity has been received"""
        return self.quantity_received >= self.quantity_expected

    def increment_received(self):
        """Increment received count and update status if complete"""
        self.quantity_received += 1
        if self.is_complete:
            self.status = ChecklistStatus.RECEIVED

    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage"""
        if self.quantity_expected == 0:
            return 0.0
        return (self.quantity_received / self.quantity_expected) * 100

