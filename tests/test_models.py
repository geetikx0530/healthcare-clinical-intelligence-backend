import pytest
from sqlalchemy import inspect, select
from app.database.connection import SessionLocal, engine
from app.models.user import User
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord
from app.models.medical_entity import MedicalEntity


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_database_connection():
    with engine.connect() as conn:
        assert conn is not None


def test_tables_exist():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "users" in tables
    assert "patients" in tables
    assert "medical_records" in tables
    assert "medical_entities" in tables


def test_user_model_insert_and_retrieve(db_session):
    test_user = User(
        name="Test Doctor",
        email="testdoctor@hospital.org",
        hashed_password="hashed_secret_password_123",
        role="clinician"
    )
    db_session.add(test_user)
    db_session.commit()

    retrieved = db_session.execute(
        select(User).where(User.email == "testdoctor@hospital.org")
    ).scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.name == "Test Doctor"
    assert retrieved.role == "clinician"

    # Cleanup
    db_session.delete(retrieved)
    db_session.commit()


def test_patient_model_insert_and_retrieve(db_session):
    test_patient = Patient(
        patient_code="PT-TEST-001",
        name="Alice Test",
        age=30,
        gender="Female",
        hospital="City Hospital",
        doctor="Dr. House",
        status="Low Risk",
        risk_score=15.5
    )
    db_session.add(test_patient)
    db_session.commit()

    retrieved = db_session.execute(
        select(Patient).where(Patient.patient_code == "PT-TEST-001")
    ).scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.name == "Alice Test"
    assert retrieved.age == 30

    # Cleanup
    db_session.delete(retrieved)
    db_session.commit()


def test_medical_record_relationship(db_session):
    patient = Patient(
        patient_code="PT-TEST-002",
        name="Bob Test",
        age=45,
        gender="Male"
    )
    record = MedicalRecord(
        record_type="Cardiology Consultation",
        diagnosis="Hypertension",
        symptoms="Chest tightness",
        medications="Lisinopril",
        vitals={"bp": "135/85", "hr": 78}
    )
    patient.records.append(record)
    db_session.add(patient)
    db_session.commit()

    retrieved_patient = db_session.execute(
        select(Patient).where(Patient.patient_code == "PT-TEST-002")
    ).scalar_one_or_none()

    assert retrieved_patient is not None
    assert len(retrieved_patient.records) == 1
    assert retrieved_patient.records[0].diagnosis == "Hypertension"
    assert retrieved_patient.records[0].vitals["bp"] == "135/85"

    # Cleanup (Cascade deletes record)
    db_session.delete(retrieved_patient)
    db_session.commit()


def test_medical_entity_relationship(db_session):
    patient = Patient(
        patient_code="PT-TEST-003",
        name="Charlie Test",
        age=55,
        gender="Male"
    )
    record = MedicalRecord(
        record_type="Lab Report",
        raw_text="Patient diagnosed with Type 2 Diabetes. Prescribed Metformin."
    )
    entity = MedicalEntity(
        entity_type="DISEASE",
        entity_text="Type 2 Diabetes",
        confidence=0.98
    )

    patient.records.append(record)
    patient.entities.append(entity)
    record.entities.append(entity)

    db_session.add(patient)
    db_session.commit()

    retrieved_patient = db_session.execute(
        select(Patient).where(Patient.patient_code == "PT-TEST-003")
    ).scalar_one_or_none()

    assert retrieved_patient is not None
    assert len(retrieved_patient.entities) == 1
    assert retrieved_patient.entities[0].entity_text == "Type 2 Diabetes"
    assert retrieved_patient.entities[0].record is not None

    # Cleanup (Cascade deletes record & entities)
    db_session.delete(retrieved_patient)
    db_session.commit()
