import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image, UnidentifiedImageError
import pytesseract
from app.core.config import settings

# Check for custom TESSERACT_CMD path in env or default installation paths
DEFAULT_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def configure_tesseract():
    """Configures pytesseract tesseract_cmd binary path if found."""
    env_path = os.getenv("TESSERACT_CMD")
    if env_path and os.path.exists(env_path):
        pytesseract.pytesseract.tesseract_cmd = env_path
        return env_path

    system_path = shutil.which("tesseract")
    if system_path:
        pytesseract.pytesseract.tesseract_cmd = system_path
        return system_path

    for path in DEFAULT_TESSERACT_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return path

    return None


def is_tesseract_available() -> bool:
    """Returns True if tesseract executable is configured and accessible."""
    cmd = configure_tesseract()
    if not cmd:
        return False
    return os.path.exists(cmd)


def perform_ocr(file_path: str, content_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Performs Tesseract OCR text extraction on an image or PDF document.
    Gracefully handles missing Tesseract binaries, corrupt files, or processing failures.
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "status": "failed",
            "extracted_text": None,
            "text_length": 0,
            "error": f"Uploaded file not found at path: {file_path}"
        }

    if not is_tesseract_available():
        return {
            "success": False,
            "status": "failed",
            "extracted_text": None,
            "text_length": 0,
            "error": "Tesseract OCR binary (tesseract.exe) is not installed or not configured in system PATH."
        }

    ext = Path(file_path).suffix.lower()

    try:
        if ext == ".pdf" or (content_type and "pdf" in content_type.lower()):
            # PDF Processing via pdf2image
            from pdf2image import convert_from_path
            try:
                images = convert_from_path(file_path)
                extracted_pages = []
                for idx, page_img in enumerate(images):
                    text = pytesseract.image_to_string(page_img)
                    extracted_pages.append(f"--- Page {idx + 1} ---\n{text}")
                
                full_text = "\n\n".join(extracted_pages).strip()
                return {
                    "success": True,
                    "status": "completed",
                    "extracted_text": full_text,
                    "text_length": len(full_text),
                    "error": None
                }
            except Exception as pdf_err:
                return {
                    "success": False,
                    "status": "failed",
                    "extracted_text": None,
                    "text_length": 0,
                    "error": f"PDF OCR conversion failed: {str(pdf_err)}"
                }
        else:
            # Image Processing via PIL & pytesseract
            try:
                with Image.open(file_path) as img:
                    text = pytesseract.image_to_string(img).strip()
                    return {
                        "success": True,
                        "status": "completed",
                        "extracted_text": text,
                        "text_length": len(text),
                        "error": None
                    }
            except UnidentifiedImageError:
                return {
                    "success": False,
                    "status": "failed",
                    "extracted_text": None,
                    "text_length": 0,
                    "error": "File is corrupt or not a valid image format."
                }

    except Exception as e:
        return {
            "success": False,
            "status": "failed",
            "extracted_text": None,
            "text_length": 0,
            "error": f"OCR processing error: {str(e)}"
        }
