"""
Intake database model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import IntakeStatus


class Intake(Base):
    """
    Intake model representing a tax-year case for a client.
    
    Each intake represents one work session for a client in a specific fiscal year.
    Status transitions: open → done (when all checklist items are received)
    """
    __tablename__ = "intakes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    client_id = Column(String(36), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=False)
    status = Column(Enum(IntakeStatus), default=IntakeStatus.OPEN, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    client = relationship("Client", back_populates="intakes")
    documents = relationship("Document", back_populates="intake", cascade="all, delete-orphan")
    checklist_items = relationship("ChecklistItem", back_populates="intake", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Intake(id={self.id}, client_id={self.client_id}, fiscal_year={self.fiscal_year}, status={self.status.value})>"

    @property
    def is_complete(self) -> bool:
        """Check if all checklist items are received"""
        if not self.checklist_items:
            return False
        return all(item.status.value == "received" for item in self.checklist_items)

    def update_status(self):
        """Update intake status based on checklist completion"""
        if self.is_complete:
            self.status = IntakeStatus.DONE
        else:
            self.status = IntakeStatus.OPEN

