"""
File handling utilities for document uploads
"""
import hashlib
import mimetypes
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile, HTTPException


def calculate_sha256(file_content: bytes) -> str:
    """
    Calculate SHA256 hash of file content.
    
    Args:
        file_content: Raw bytes of the file
        
    Returns:
        Hexadecimal SHA256 hash string (64 characters)
    """
    return hashlib.sha256(file_content).hexdigest()


def validate_file_type(filename: str, allowed_extensions: set) -> str:
    """
    Validate file extension and determine MIME type.
    
    Args:
        filename: Name of the uploaded file
        allowed_extensions: Set of allowed file extensions (e.g., {'.pdf', '.png', '.jpg'})
        
    Returns:
        MIME type string
        
    Raises:
        HTTPException 400: If file extension is not allowed
    """
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    mime_type = mimetypes.guess_type(filename)[0]
    if not mime_type:
        mime_type_map = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg'
        }
        mime_type = mime_type_map.get(file_ext, 'application/octet-stream')
    
    return mime_type


def validate_file_size(file_size: int, max_size: int) -> None:
    """
    Validate file size is within allowed limit.
    
    Args:
        file_size: Size of file in bytes
        max_size: Maximum allowed size in bytes
        
    Raises:
        HTTPException 413: If file size exceeds maximum
    """
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File size {actual_mb:.2f}MB exceeds maximum allowed size of {max_mb:.2f}MB"
        )


async def save_uploaded_file(
    file: UploadFile,
    bucket_dir: Path,
    intake_id: str,
    allowed_extensions: set,
    max_file_size: int
) -> Tuple[bytes, str, str, int]:
    """
    Save uploaded file to bucket directory and return file metadata.
    
    Args:
        file: FastAPI UploadFile object
        bucket_dir: Directory to store files
        intake_id: Intake UUID for organizing files
        allowed_extensions: Set of allowed file extensions
        max_file_size: Maximum file size in bytes
        
    Returns:
        Tuple of (file_content, stored_path, mime_type, size_bytes)
        
    Raises:
        HTTPException 400: If file type not allowed
        HTTPException 413: If file size exceeds limit
    """
    file_content = await file.read()
    file_size = len(file_content)
    
    validate_file_size(file_size, max_file_size)
    mime_type = validate_file_type(file.filename, allowed_extensions)
    
    intake_bucket = bucket_dir / intake_id
    intake_bucket.mkdir(parents=True, exist_ok=True)
    
    sha256_hash = calculate_sha256(file_content)
    file_ext = Path(file.filename).suffix.lower()
    stored_filename = f"{sha256_hash}{file_ext}"
    stored_path = intake_bucket / stored_filename
    
    with open(stored_path, 'wb') as f:
        f.write(file_content)
    
    return file_content, str(stored_path), mime_type, file_size

