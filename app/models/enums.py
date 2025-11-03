"""
Enum definitions for database models
"""
import enum


class ClientComplexity(str, enum.Enum):
    """Client complexity levels determining expected document count"""
    SIMPLE = "simple"      # T4 + ID (2 documents)
    AVERAGE = "average"    # T4 + ID + 2 receipts (4 documents)
    COMPLEX = "complex"    # T4 + ID + 5 receipts (8 documents)


class IntakeStatus(str, enum.Enum):
    """Intake processing status"""
    OPEN = "open"          # Intake is still being processed
    DONE = "done"          # All required documents received and processed


class DocKind(str, enum.Enum):
    """Document classification types"""
    T4 = "T4"              # Canadian T4 tax form
    RECEIPT = "receipt"    # Receipt document
    ID = "id"              # ID card or driver's license
    UNKNOWN = "unknown"    # Unclassified document


class ChecklistStatus(str, enum.Enum):
    """Checklist item status"""
    MISSING = "missing"    # Document not yet received
    RECEIVED = "received"  # Document received and extracted

