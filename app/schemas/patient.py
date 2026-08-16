from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatientBase(BaseModel):
    patient_code: str = Field(..., description="Unique patient identifier, e.g. PT-1001")
    name: str = Field(..., description="Full name of patient")
    age: Optional[int] = Field(None, ge=0, le=150, description="Patient age between 0 and 150")
    gender: Optional[str] = Field(None, description="Gender identity")
    hospital: Optional[str] = Field(None, description="Hospital name")
    doctor: Optional[str] = Field(None, description="Assigned doctor name")
    date_of_registration: Optional[datetime] = Field(None, description="Date patient was registered")
    status: Optional[str] = Field(None, description="Patient status e.g. High Risk, Low Risk")
    risk_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Risk percentage (0-100)")

    @field_validator("name", "patient_code", mode="before")
    @classmethod
    def strip_and_validate_non_empty(cls, v: str) -> str:
        if isinstance(v, str):
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Field cannot be empty or whitespace only")
            return trimmed
        return v

    @field_validator("gender", "hospital", "doctor", "status", mode="before")
    @classmethod
    def strip_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip() or None
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    patient_code: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = None
    hospital: Optional[str] = None
    doctor: Optional[str] = None
    date_of_registration: Optional[datetime] = None
    status: Optional[str] = None
    risk_score: Optional[float] = Field(None, ge=0.0, le=100.0)

    @field_validator("name", "patient_code", mode="before")
    @classmethod
    def strip_and_validate_non_empty_update(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and isinstance(v, str):
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Field cannot be empty or whitespace only")
            return trimmed
        return v


class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
