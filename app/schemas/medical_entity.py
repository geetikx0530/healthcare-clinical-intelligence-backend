from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MedicalEntityBase(BaseModel):
    patient_id: int = Field(..., description="ID of patient associated with entity")
    medical_record_id: Optional[int] = Field(None, description="Optional associated record ID")
    entity_type: str = Field(..., description="e.g. DISEASE, SYMPTOM, MEDICATION, LAB_TEST")
    entity_text: str = Field(..., description="Extracted clinical entity text")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="NLP confidence score (0.0 - 1.0)")

    @field_validator("entity_type", "entity_text", mode="before")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if isinstance(v, str):
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Field cannot be empty or whitespace only")
            return trimmed
        return v


class MedicalEntityCreate(MedicalEntityBase):
    pass


class MedicalEntityResponse(MedicalEntityBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
