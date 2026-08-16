import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse
from app.schemas.auth import UserCreate, UserResponse
from app.schemas.medical_record import MedicalRecordCreate, MedicalRecordResponse
from app.schemas.medical_entity import MedicalEntityCreate, MedicalEntityResponse
from app.models.user import User


# 1. Valid patient creation schema
def test_valid_patient_create():
    patient = PatientCreate(
        patient_code="PT-1001",
        name="  John Doe  ",
        age=45,
        gender="Male",
        hospital="City General",
        doctor="Dr. Smith",
        status="High Risk",
        risk_score=85.5
    )
    assert patient.name == "John Doe"  # Trimmed
    assert patient.patient_code == "PT-1001"
    assert patient.age == 45
    assert patient.risk_score == 85.5


# 2. Invalid empty patient name
def test_invalid_empty_patient_name():
    with pytest.raises(ValidationError):
        PatientCreate(
            patient_code="PT-1001",
            name="   "
        )


# 3. Invalid age (<0 or >150)
def test_invalid_patient_age():
    with pytest.raises(ValidationError):
        PatientCreate(
            patient_code="PT-1001",
            name="John Doe",
            age=-5
        )
    with pytest.raises(ValidationError):
        PatientCreate(
            patient_code="PT-1001",
            name="John Doe",
            age=200
        )


# 4. Invalid risk score (<0 or >100)
def test_invalid_patient_risk_score():
    with pytest.raises(ValidationError):
        PatientCreate(
            patient_code="PT-1001",
            name="John Doe",
            risk_score=150.0
        )


# 5. Patient update with partial fields
def test_patient_update_partial():
    update_data = PatientUpdate(status="Low Risk", risk_score=20.0)
    assert update_data.status == "Low Risk"
    assert update_data.name is None


# 6. User creation schema
def test_valid_user_create():
    user = UserCreate(
        name="  Dr. Jane  ",
        email="jane@hospital.org",
        password="secretpassword123"
    )
    assert user.name == "Dr. Jane"
    assert user.email == "jane@hospital.org"


# 7. User response does not expose password/hash
def test_user_response_security():
    db_user = User(
        id=1,
        name="Dr. Jane",
        email="jane@hospital.org",
        hashed_password="secret_hash_not_exposed",
        role="clinician",
        created_at=datetime.now(timezone.utc)
    )
    response = UserResponse.model_validate(db_user)
    response_dict = response.model_dump()
    assert "hashed_password" not in response_dict
    assert "password" not in response_dict
    assert response_dict["email"] == "jane@hospital.org"


# 8. Medical record schema
def test_valid_medical_record_create():
    record = MedicalRecordCreate(
        patient_id=1,
        record_type="Cardiology",
        diagnosis="Arrhythmia",
        vitals={"bp": "120/80", "hr": 72}
    )
    assert record.patient_id == 1
    assert record.diagnosis == "Arrhythmia"
    assert record.vitals["hr"] == 72


# 9. Medical entity schema
def test_valid_medical_entity_create():
    entity = MedicalEntityCreate(
        patient_id=1,
        entity_type="DISEASE",
        entity_text="Type 2 Diabetes",
        confidence=0.95
    )
    assert entity.entity_type == "DISEASE"
    assert entity.entity_text == "Type 2 Diabetes"
    assert entity.confidence == 0.95


# 10. Invalid entity confidence (<0 or >1)
def test_invalid_medical_entity_confidence():
    with pytest.raises(ValidationError):
        MedicalEntityCreate(
            patient_id=1,
            entity_type="DISEASE",
            entity_text="Type 2 Diabetes",
            confidence=1.5
        )
