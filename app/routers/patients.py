from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse
from app.core.security import get_current_user

router = APIRouter(
    prefix="/api/patients",
    tags=["Patients"]
)


@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new patient",
    description="Registers a new patient record in PostgreSQL after validating input and checking for duplicate patient code."
)
def create_patient(
    patient_in: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check for existing patient_code
    existing = db.execute(
        select(Patient).where(Patient.patient_code == patient_in.patient_code)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Patient with code '{patient_in.patient_code}' already exists."
        )

    patient_data = patient_in.model_dump()
    new_patient = Patient(**patient_data)

    try:
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction error while creating patient."
        )

    patient_response = PatientResponse.model_validate(new_patient)
    return {
        "success": True,
        "data": patient_response
    }


@router.get(
    "",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="List all patients",
    description="Returns a paginated list of patients from PostgreSQL database."
)
def get_patients(
    page: int = Query(1, ge=1, description="Page number starting at 1"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Total count
    total_count = db.execute(select(func.count(Patient.id))).scalar() or 0

    # Paginated results
    offset = (page - 1) * limit
    patients = db.execute(
        select(Patient).order_by(Patient.id.desc()).offset(offset).limit(limit)
    ).scalars().all()

    patient_responses = [PatientResponse.model_validate(p) for p in patients]

    return {
        "success": True,
        "data": patient_responses,
        "items": patient_responses,
        "total": total_count,
        "page": page,
        "limit": limit
    }


@router.get(
    "/search",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Search patients",
    description="Performs a case-insensitive search across patient_code, name, hospital, and doctor fields."
)
def search_patients(
    query: str = Query(..., min_length=1, description="Search term"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    search_pattern = f"%{query.strip()}%"

    results = db.execute(
        select(Patient).where(
            or_(
                Patient.patient_code.ilike(search_pattern),
                Patient.name.ilike(search_pattern),
                Patient.hospital.ilike(search_pattern),
                Patient.doctor.ilike(search_pattern)
            )
        ).order_by(Patient.name.asc())
    ).scalars().all()

    patient_responses = [PatientResponse.model_validate(p) for p in results]

    return {
        "success": True,
        "count": len(patient_responses),
        "data": patient_responses
    }


@router.get(
    "/{patient_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get single patient by ID",
    description="Retrieves patient details by primary key ID."
)
def get_patient_by_id(
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

    return {
        "success": True,
        "data": PatientResponse.model_validate(patient)
    }


@router.put(
    "/{patient_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Update patient",
    description="Updates fields for an existing patient by ID."
)
def update_patient(
    patient_id: int,
    patient_in: PatientUpdate,
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

    update_data = patient_in.model_dump(exclude_unset=True)

    # Check patient_code uniqueness if updating patient_code
    if "patient_code" in update_data and update_data["patient_code"] != patient.patient_code:
        code_conflict = db.execute(
            select(Patient).where(
                Patient.patient_code == update_data["patient_code"],
                Patient.id != patient_id
            )
        ).scalar_one_or_none()

        if code_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Patient code '{update_data['patient_code']}' is already in use by another patient."
            )

    for field, value in update_data.items():
        setattr(patient, field, value)

    patient.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(patient)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction error while updating patient."
        )

    return {
        "success": True,
        "data": PatientResponse.model_validate(patient)
    }


@router.delete(
    "/{patient_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Delete patient",
    description="Deletes a patient record by ID. Cascades deletion to associated medical records and entities."
)
def delete_patient(
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

    try:
        db.delete(patient)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction error while deleting patient."
        )

    return {
        "success": True,
        "message": f"Patient with ID {patient_id} deleted successfully."
    }
