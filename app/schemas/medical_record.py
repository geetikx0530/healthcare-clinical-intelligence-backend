from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class MedicalRecordBase(BaseModel):
    patient_id: int = Field(..., description="ID of patient associated with record")
    record_type: Optional[str] = Field(None, description="e.g. Cardiology, Radiology, Lab Report")
    diagnosis: Optional[str] = None
    symptoms: Optional[str] = None
    medications: Optional[str] = None
    allergies: Optional[str] = None
    medical_history: Optional[str] = None
    vitals: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None


class MedicalRecordCreate(MedicalRecordBase):
    pass


class MedicalRecordUpdate(BaseModel):
    record_type: Optional[str] = None
    diagnosis: Optional[str] = None
    symptoms: Optional[str] = None
    medications: Optional[str] = None
    allergies: Optional[str] = None
    medical_history: Optional[str] = None
    vitals: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None


class MedicalRecordResponse(MedicalRecordBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
