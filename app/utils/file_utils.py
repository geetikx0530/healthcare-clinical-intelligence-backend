import os
import uuid
from typing import Optional
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/jpg", "image/png"}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


def validate_file_type(filename: str, content_type: Optional[str] = None) -> str:
    """Validates that filename extension and MIME content type are allowed."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    
    if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported MIME type '{content_type}'. Allowed types: PDF, PNG, JPEG."
        )
    return ext


def validate_file_size(content: bytes) -> int:
    """Validates file size is within reasonable limit (10MB)."""
    size = len(content)
    if size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size ({size / (1024*1024):.2f} MB) exceeds maximum allowed limit of 10 MB."
        )
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )
    return size


def save_upload_file(file: UploadFile, content: bytes) -> tuple[str, str]:
    """
    Saves file bytes to UPLOAD_DIR with a unique UUID filename.
    Returns (relative_filepath, safe_filename).
    """
    ext = validate_file_type(file.filename or "file.pdf", file.content_type)
    validate_file_size(content)

    upload_dir_path = Path(settings.UPLOAD_DIR)
    upload_dir_path.mkdir(parents=True, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    destination_path = upload_dir_path / unique_filename

    with open(destination_path, "wb") as f:
        f.write(content)

    relative_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    return relative_path, unique_filename
