"""
Client database model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import ClientComplexity


class Client(Base):
    """
    Client model representing an individual whose complexity determines expected document count.
    
    Complexity levels:
    - simple: T4 + ID (2 documents)
    - average: T4 + ID + 2 receipts (4 documents)
    - complex: T4 + ID + 5 receipts (8 documents)
    """
    __tablename__ = "clients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    complexity = Column(Enum(ClientComplexity), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    intakes = relationship("Intake", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Client(id={self.id}, name={self.name}, complexity={self.complexity.value})>"

    @property
    def expected_document_count(self) -> int:
        """Calculate expected document count based on complexity"""
        if self.complexity == ClientComplexity.SIMPLE:
            return 2  # T4 + ID
        elif self.complexity == ClientComplexity.AVERAGE:
            return 4  # T4 + ID + 2 receipts
        elif self.complexity == ClientComplexity.COMPLEX:
            return 8  # T4 + ID + 5 receipts
        return 0

    @property
    def expected_receipt_count(self) -> int:
        """Calculate expected receipt count based on complexity"""
        if self.complexity == ClientComplexity.SIMPLE:
            return 0
        elif self.complexity == ClientComplexity.AVERAGE:
            return 2
        elif self.complexity == ClientComplexity.COMPLEX:
            return 5
        return 0

