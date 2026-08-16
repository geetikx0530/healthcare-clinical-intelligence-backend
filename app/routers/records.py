import os
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord
from app.models.medical_entity import MedicalEntity
from app.models.user import User
from app.schemas.medical_record import MedicalRecordResponse
from app.core.security import get_current_user
from app.utils.file_utils import save_upload_file
from app.services.ocr_service import perform_ocr
from app.services.nlp_service import extract_medical_entities



router = APIRouter(
    tags=["Medical Records"]
)


@router.post(
    "/api/patients/{patient_id}/records/upload",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Upload medical document for patient",
    description="Validates and uploads a PDF or image medical document (max 10MB) for an existing patient."
)
async def upload_medical_record(
    patient_id: int,
    file: UploadFile = File(..., description="PDF or Image file (PNG, JPEG)"),
    record_type: Optional[str] = Form(None, description="Document classification e.g. Lab Report, Radiology"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify patient exists
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id)
    ).scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found."
        )

    # 2. Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error reading uploaded file: {str(e)}"
        )

    # 3. Validate and save file safely
    relative_path, unique_filename = save_upload_file(file, content)

    # 4. Create MedicalRecord DB entry
    metadata = {
        "original_filename": file.filename,
        "content_type": file.content_type,
        "file_size": len(content),
        "file_path": relative_path,
        "unique_filename": unique_filename
    }

    new_record = MedicalRecord(
        patient_id=patient_id,
        record_type=record_type or "Medical Document",
        vitals=metadata,
        raw_text=None  # To be populated by OCR in Phase 9
    )

    try:
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
    except Exception as e:
        db.rollback()
        # Clean up saved file if DB commit fails
        if os.path.exists(relative_path):
            os.remove(relative_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while saving medical record metadata."
        )

    return {
        "success": True,
        "data": MedicalRecordResponse.model_validate(new_record)
    }


@router.get(
    "/api/patients/{patient_id}/records",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get all medical records for a patient",
    description="Retrieves all uploaded medical records for a specified patient."
)
def get_patient_records(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.execute(
        select(Patient).where(Patient.id == patient_id)
    ).scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found."
        )

    records = db.execute(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .order_by(MedicalRecord.created_at.desc())
    ).scalars().all()

    record_responses = [MedicalRecordResponse.model_validate(r) for r in records]

    return {
        "success": True,
        "count": len(record_responses),
        "data": record_responses
    }


@router.get(
    "/api/records/{record_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get single medical record by ID",
    description="Retrieves medical record details by ID."
)
def get_record_by_id(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    record = db.execute(
        select(MedicalRecord).where(MedicalRecord.id == record_id)
    ).scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medical record with ID {record_id} not found."
        )

    return {
        "success": True,
        "data": MedicalRecordResponse.model_validate(record)
    }


@router.delete(
    "/api/records/{record_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Delete medical record",
    description="Deletes a medical record and its stored file."
)
def delete_medical_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    record = db.execute(
        select(MedicalRecord).where(MedicalRecord.id == record_id)
    ).scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medical record with ID {record_id} not found."
        )

    # Delete local file if it exists
    if record.vitals and isinstance(record.vitals, dict) and "file_path" in record.vitals:
        file_path = record.vitals["file_path"]
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    try:
        db.delete(record)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction error while deleting medical record."
        )

    return {
        "success": True,
        "message": f"Medical record with ID {record_id} deleted successfully."
    }


@router.post(
    "/api/records/{record_id}/process",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Process medical record with OCR",
    description="Extracts raw text from an uploaded document using Tesseract OCR and stores it in raw_text."
)
def process_medical_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify record exists
    record = db.execute(
        select(MedicalRecord).where(MedicalRecord.id == record_id)
    ).scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medical record with ID {record_id} not found."
        )

    # 2. Extract file path & content_type from vitals metadata
    file_path = None
    content_type = None
    if record.vitals and isinstance(record.vitals, dict):
        file_path = record.vitals.get("file_path")
        content_type = record.vitals.get("content_type")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Associated uploaded document file was not found on server storage."
        )

    # 3. Perform OCR
    ocr_result = perform_ocr(file_path, content_type)

    # 4. If OCR succeeded, update record.raw_text
    if ocr_result["success"] and ocr_result["extracted_text"]:
        record.raw_text = ocr_result["extracted_text"]
        try:
            db.commit()
            db.refresh(record)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error saving OCR extracted text."
            )

    return {
        "success": ocr_result["success"],
        "data": {
            "record_id": record.id,
            "processing_status": ocr_result["status"],
            "extracted_text_length": ocr_result["text_length"],
            "ocr_succeeded": ocr_result["success"],
            "extracted_text": record.raw_text or ocr_result.get("extracted_text"),
            "error": ocr_result.get("error")
        }
    }


@router.post(
    "/api/records/{record_id}/analyze",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Analyze medical record with NLP service",
    description="Extracts structured medical entities (symptoms, diagnoses, medications, dosages, treatment plans) from raw_text using NLP and stores them in database."
)
def analyze_medical_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify record exists
    record = db.execute(
        select(MedicalRecord).where(MedicalRecord.id == record_id)
    ).scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medical record with ID {record_id} not found."
        )

    # 2. Verify raw_text exists
    if not record.raw_text or not record.raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Medical record has no raw_text to analyze. Process document with OCR first."
        )

    # 3. Run NLP extraction
    entities_data = extract_medical_entities(record.raw_text)

    # 4. Update MedicalRecord fields & vitals metadata JSON
    if entities_data["symptoms"]:
        record.symptoms = "; ".join(entities_data["symptoms"])
    if entities_data["diagnoses"]:
        record.diagnosis = "; ".join(entities_data["diagnoses"])
    if entities_data["medications"]:
        record.medications = "; ".join(entities_data["medications"])

    current_vitals = dict(record.vitals or {})
    current_vitals["nlp_analysis"] = {
        "symptoms": entities_data["symptoms"],
        "diagnoses": entities_data["diagnoses"],
        "medications": entities_data["medications"],
        "dosages": entities_data["dosages"],
        "treatment_plans": entities_data["treatment_plans"],
        "medical_conditions": entities_data["medical_conditions"],
        "important_clinical_findings": entities_data["important_clinical_findings"]
    }
    record.vitals = current_vitals

    # 5. Persist granular MedicalEntity rows to medical_entities table
    saved_entities = []
    for item in entities_data.get("entities", []):
        entity = MedicalEntity(
            patient_id=record.patient_id,
            medical_record_id=record.id,
            entity_type=item["entity_type"],
            entity_text=item["entity_text"],
            confidence=item.get("confidence", 0.9)
        )
        db.add(entity)
        saved_entities.append(entity)

    try:
        db.commit()
        db.refresh(record)
        for e in saved_entities:
            db.refresh(e)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error saving NLP medical entities."
        )

    return {
        "success": True,
        "data": {
            "record_id": record.id,
            "patient_id": record.patient_id,
            "symptoms": entities_data["symptoms"],
            "diagnoses": entities_data["diagnoses"],
            "medications": entities_data["medications"],
            "dosages": entities_data["dosages"],
            "treatment_plans": entities_data["treatment_plans"],
            "medical_conditions": entities_data["medical_conditions"],
            "important_clinical_findings": entities_data["important_clinical_findings"],
            "entities_count": len(saved_entities),
            "entities": [
                {
                    "id": e.id,
                    "entity_type": e.entity_type,
                    "entity_text": e.entity_text,
                    "confidence": e.confidence
                }
                for e in saved_entities
            ]
        }
    }

