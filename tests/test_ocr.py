import os
import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.database.connection import SessionLocal
from app.models.user import User
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord

client = TestClient(app)


@pytest.fixture(scope="module")
def ocr_setup():
    doc_email = "ocr_test_doc@hospital.org"
    doc_password = "docpassword123"
    client.post("/api/auth/register", json={"name": "Dr. OCR Tester", "email": doc_email, "password": doc_password})
    login_res = client.post("/api/auth/login", json={"email": doc_email, "password": doc_password})
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patient_res = client.post("/api/patients", headers=headers, json={"patient_code": "PT-OCR-001", "name": "OCR Patient"})
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


# 1. Unauthenticated process request (401)
def test_process_unauthenticated(ocr_setup):
    res = client.post("/api/records/9999/process")
    assert res.status_code == 401


# 2. Nonexistent record process (404)
def test_process_nonexistent_record(ocr_setup):
    headers = ocr_setup["headers"]
    res = client.post("/api/records/999999/process", headers=headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


# 3. Missing uploaded file (400)
def test_process_missing_file(ocr_setup):
    headers = ocr_setup["headers"]
    patient_id = ocr_setup["patient_id"]

    # Create medical record with missing file path in vitals
    db = SessionLocal()
    rec = MedicalRecord(
        patient_id=patient_id,
        record_type="Test",
        vitals={"file_path": "uploads/non_existent_file_xyz.pdf"}
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec_id = rec.id
    db.close()

    res = client.post(f"/api/records/{rec_id}/process", headers=headers)
    assert res.status_code == 400
    assert "associated uploaded document file was not found" in res.json()["detail"].lower()

    # Cleanup
    client.delete(f"/api/records/{rec_id}", headers=headers)


# 4. Graceful handling when Tesseract is missing
@patch("app.services.ocr_service.is_tesseract_available", return_value=False)
def test_process_tesseract_missing_response(mock_is_avail, ocr_setup):
    headers = ocr_setup["headers"]
    patient_id = ocr_setup["patient_id"]

    pdf_bytes = b"%PDF-1.4 Test PDF for OCR missing binary test"
    upload_res = client.post(
        f"/api/patients/{patient_id}/records/upload",
        headers=headers,
        files={"file": ("test_ocr.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    record_id = upload_res.json()["data"]["id"]

    res = client.post(f"/api/records/{record_id}/process", headers=headers)
    assert res.status_code == 200
    json_data = res.json()
    # When Tesseract is set to missing, status should report failed with informative error
    assert json_data["success"] is False
    assert json_data["data"]["processing_status"] == "failed"
    assert "Tesseract" in json_data["data"]["error"]

    # Cleanup
    client.delete(f"/api/records/{record_id}", headers=headers)


# 5. Successful OCR processing with mocked OCR engine & raw_text storage
@patch("app.routers.records.perform_ocr")
def test_process_successful_ocr_mock(mock_ocr, ocr_setup):
    mock_ocr.return_value = {
        "success": True,
        "status": "completed",
        "extracted_text": "Patient has Type 2 Diabetes and Hypertension. Prescribed Metformin.",
        "text_length": 65,
        "error": None
    }

    headers = ocr_setup["headers"]
    patient_id = ocr_setup["patient_id"]

    png_bytes = b"\x89PNG\r\n\x1a\nFake PNG content for OCR"
    upload_res = client.post(
        f"/api/patients/{patient_id}/records/upload",
        headers=headers,
        files={"file": ("mock_scan.png", io.BytesIO(png_bytes), "image/png")}
    )
    record_id = upload_res.json()["data"]["id"]

    res = client.post(f"/api/records/{record_id}/process", headers=headers)
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["success"] is True
    assert json_data["data"]["ocr_succeeded"] is True
    assert "Type 2 Diabetes" in json_data["data"]["extracted_text"]

    # Verify database persistence of raw_text
    db = SessionLocal()
    db_rec = db.execute(select(MedicalRecord).where(MedicalRecord.id == record_id)).scalar_one()
    assert db_rec.raw_text == "Patient has Type 2 Diabetes and Hypertension. Prescribed Metformin."
    db.close()

    # Cleanup
    client.delete(f"/api/records/{record_id}", headers=headers)
