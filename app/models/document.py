"""
Document database model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Enum, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import DocKind


class Document(Base):
    """
    Document model representing an uploaded file in an intake.
    
    Features:
    - SHA256 hash for duplicate detection
    - Document classification (T4, receipt, id, unknown)
    - Extracted data stored as JSON
    - Unique constraint on (intake_id, sha256) to prevent duplicates within same intake
    """
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    intake_id = Column(String(36), ForeignKey("intakes.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)  # SHA256 hash for duplicate detection
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    stored_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    doc_kind = Column(Enum(DocKind), default=DocKind.UNKNOWN, nullable=False)
    extracted_data = Column(JSON, nullable=True)  # Stores extracted fields as JSON

    # Relationships
    intake = relationship("Intake", back_populates="documents")

    # Indexes
    __table_args__ = (
        # Unique constraint: prevent duplicate uploads within same intake
        Index('idx_intake_sha256', 'intake_id', 'sha256', unique=True),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename}, doc_kind={self.doc_kind.value})>"

    @property
    def is_classified(self) -> bool:
        """Check if document has been classified"""
        return self.doc_kind != DocKind.UNKNOWN

    @property
    def is_extracted(self) -> bool:
        """Check if data has been extracted from document"""
        return self.extracted_data is not None and len(self.extracted_data) > 0

    @property
    def file_extension(self) -> str:
        """Get file extension from filename"""
        return self.filename.split('.')[-1].lower() if '.' in self.filename else ''

