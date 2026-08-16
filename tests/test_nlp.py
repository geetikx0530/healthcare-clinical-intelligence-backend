import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.database.connection import SessionLocal
from app.models.user import User
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord
from app.models.medical_entity import MedicalEntity
from app.services.nlp_service import extract_medical_entities

client = TestClient(app)


@pytest.fixture(scope="module")
def nlp_setup():
    doc_email = "nlp_test_doc@hospital.org"
    doc_password = "docpassword123"
    client.post("/api/auth/register", json={"name": "Dr. NLP Tester", "email": doc_email, "password": doc_password})
    login_res = client.post("/api/auth/login", json={"email": doc_email, "password": doc_password})
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patient_res = client.post("/api/patients", headers=headers, json={"patient_code": "PT-NLP-001", "name": "NLP Patient"})
    patient_id = patient_res.json()["data"]["id"]

    yield {"headers": headers, "patient_id": patient_id, "email": doc_email}

    # Cleanup
    client.delete(f"/api/patients/{patient_id}", headers=headers)
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == doc_email)).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 1. Unit Test: Direct NLP Extraction Function (Basic & Structured)
def test_extract_medical_entities_basic():
    sample_text = (
        "CHIEF COMPLAINT:\n"
        "Shortness of breath and fever for 2 days.\n\n"
        "DIAGNOSIS:\n"
        "Acute Bronchitis and Hypertension.\n\n"
        "MEDICATIONS:\n"
        "1. Amoxicillin 500mg - Take 1 tablet 3 times daily.\n"
        "2. Lisinopril 10mg - Take 1 tablet daily.\n\n"
        "TREATMENT PLAN:\n"
        "Rest, drink fluids, and follow up in 1 week."
    )

    result = extract_medical_entities(sample_text)

    assert len(result["symptoms"]) > 0
    assert any("shortness of breath" in s.lower() for s in result["symptoms"])
    assert len(result["diagnoses"]) > 0
    assert any("bronchitis" in d.lower() for d in result["diagnoses"])
    assert len(result["medications"]) > 0
    assert any("amoxicillin" in m.lower() for m in result["medications"])
    assert len(result["dosages"]) > 0
    assert "500mg" in result["dosages"] or "10mg" in result["dosages"]
    assert len(result["treatment_plans"]) > 0
    assert len(result["entities"]) > 0


# 2. Unit Test: Empty / Missing Text Handling
def test_extract_medical_entities_empty():
    res_none = extract_medical_entities(None)
    assert res_none["symptoms"] == []
    assert res_none["diagnoses"] == []
    assert res_none["medications"] == []
    assert res_none["entities"] == []

    res_empty = extract_medical_entities("   ")
    assert res_empty["symptoms"] == []
    assert res_empty["diagnoses"] == []
    assert res_empty["medications"] == []
    assert res_empty["entities"] == []


# 3. API Test: Unauthenticated Request (401)
def test_analyze_unauthenticated(nlp_setup):
    res = client.post("/api/records/9999/analyze")
    assert res.status_code == 401


# 4. API Test: Nonexistent Record (404)
def test_analyze_nonexistent_record(nlp_setup):
    headers = nlp_setup["headers"]
    res = client.post("/api/records/999999/analyze", headers=headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# 5. API Test: Missing raw_text in MedicalRecord (400)
def test_analyze_missing_raw_text(nlp_setup):
    headers = nlp_setup["headers"]
    patient_id = nlp_setup["patient_id"]

    db = SessionLocal()
    rec = MedicalRecord(
        patient_id=patient_id,
        record_type="Test Record",
        raw_text=None
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec_id = rec.id
    db.close()

    res = client.post(f"/api/records/{rec_id}/analyze", headers=headers)
    assert res.status_code == 400
    assert "no raw_text" in res.json()["detail"].lower()

    # Cleanup
    client.delete(f"/api/records/{rec_id}", headers=headers)


# 6. API Test: Successful NLP Entity Extraction (200 OK)
def test_analyze_record_success(nlp_setup):
    headers = nlp_setup["headers"]
    patient_id = nlp_setup["patient_id"]

    sample_ocr_text = (
        "CLINICAL ASSESSMENT REPORT\n"
        "CHIEF COMPLAINT:\n"
        "Chest pain, shortness of breath, and severe headache.\n\n"
        "DIAGNOSIS:\n"
        "Hypertension and Mild Asthma Exacerbation.\n\n"
        "PRESCRIPTION:\n"
        "Albuterol 90mcg Inhaler 2 puffs every 4 hours.\n"
        "Lisinopril 10mg daily.\n\n"
        "TREATMENT PLAN:\n"
        "Monitor blood pressure daily and return in 14 days."
    )

    db = SessionLocal()
    rec = MedicalRecord(
        patient_id=patient_id,
        record_type="Cardiology Consultation",
        raw_text=sample_ocr_text
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec_id = rec.id
    db.close()

    res = client.post(f"/api/records/{rec_id}/analyze", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["record_id"] == rec_id
    assert data["patient_id"] == patient_id
    assert len(data["symptoms"]) > 0
    assert len(data["diagnoses"]) > 0
    assert len(data["medications"]) > 0
    assert len(data["dosages"]) > 0
    assert len(data["treatment_plans"]) > 0
    assert data["entities_count"] > 0

    # Cleanup
    client.delete(f"/api/records/{rec_id}", headers=headers)


# 7. Category Extraction Tests (Symptoms, Diagnosis, Medication, Treatment Plan)
def test_analyze_category_extractions(nlp_setup):
    headers = nlp_setup["headers"]
    patient_id = nlp_setup["patient_id"]

    sample_ocr_text = (
        "SYMPTOMS: Persistent cough and fever.\n"
        "DIAGNOSIS: Acute Bronchitis.\n"
        "MEDICATIONS: Amoxicillin 500mg twice daily.\n"
        "TREATMENT PLAN: Complete full 7-day antibiotic course and rest."
    )

    db = SessionLocal()
    rec = MedicalRecord(patient_id=patient_id, record_type="Pulmonology", raw_text=sample_ocr_text)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec_id = rec.id
    db.close()

    res = client.post(f"/api/records/{rec_id}/analyze", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]

    # Test symptoms extraction
    assert any("cough" in s.lower() for s in data["symptoms"])
    # Test diagnosis extraction
    assert any("bronchitis" in d.lower() for d in data["diagnoses"])
    # Test medication extraction
    assert any("amoxicillin" in m.lower() for m in data["medications"])
    # Test treatment plan extraction
    assert any("antibiotic" in tp.lower() or "rest" in tp.lower() for tp in data["treatment_plans"])

    client.delete(f"/api/records/{rec_id}", headers=headers)


# 8. Database Persistence Test (MedicalRecord columns, vitals JSON, MedicalEntity table)
def test_analyze_db_persistence(nlp_setup):
    headers = nlp_setup["headers"]
    patient_id = nlp_setup["patient_id"]

    sample_ocr_text = (
        "SYMPTOMS: Wheezing and shortness of breath.\n"
        "DIAGNOSIS: Asthma.\n"
        "MEDICATIONS: Albuterol inhaler as needed."
    )

    db = SessionLocal()
    rec = MedicalRecord(patient_id=patient_id, record_type="General", raw_text=sample_ocr_text)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec_id = rec.id
    db.close()

    res = client.post(f"/api/records/{rec_id}/analyze", headers=headers)
    assert res.status_code == 200

    # Query DB to check persistence
    db = SessionLocal()
    db_rec = db.execute(select(MedicalRecord).where(MedicalRecord.id == rec_id)).scalar_one()
    assert db_rec.symptoms is not None
    assert db_rec.diagnosis is not None
    assert db_rec.medications is not None
    assert db_rec.vitals is not None
    assert "nlp_analysis" in db_rec.vitals

    # Check medical_entities table persistence
    entities = db.execute(select(MedicalEntity).where(MedicalEntity.medical_record_id == rec_id)).scalars().all()
    assert len(entities) > 0
    entity_types = [e.entity_type for e in entities]
    assert "SYMPTOM" in entity_types
    assert "DIAGNOSIS" in entity_types
    assert "MEDICATION" in entity_types

    db.close()

    client.delete(f"/api/records/{rec_id}", headers=headers)
