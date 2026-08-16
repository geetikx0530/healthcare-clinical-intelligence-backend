import os
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.database.connection import SessionLocal
from app.models.user import User
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_data():
    # Register & Login test doc
    doc_email = "record_doc@hospital.org"
    doc_password = "docpassword123"
    client.post(
        "/api/auth/register",
        json={"name": "Dr. Record Tester", "email": doc_email, "password": doc_password}
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email": doc_email, "password": doc_password}
    )
    token = login_res.json()["data"]["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Create test patient
    patient_res = client.post(
        "/api/patients",
        headers=auth_headers,
        json={"patient_code": "PT-REC-001", "name": "Record Patient", "age": 42}
    )
    patient_id = patient_res.json()["data"]["id"]

    yield {"headers": auth_headers, "patient_id": patient_id, "doc_email": doc_email}

    # Cleanup patient & user
    client.delete(f"/api/patients/{patient_id}", headers=auth_headers)
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == doc_email)).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 1. Successful PDF upload
def test_successful_pdf_upload(setup_data):
    headers = setup_data["headers"]
    patient_id = setup_data["patient_id"]

    pdf_bytes = b"%PDF-1.4 Fake PDF Content for medical record testing..."
    files = {"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"record_type": "Lab Report"}

    res = client.post(
        f"/api/patients/{patient_id}/records/upload",
        headers=headers,
        files=files,
        data=data
    )

    assert res.status_code == 201
    json_data = res.json()
    assert json_data["success"] is True
    assert json_data["data"]["patient_id"] == patient_id
    assert json_data["data"]["record_type"] == "Lab Report"
    assert "original_filename" in json_data["data"]["vitals"]
    assert json_data["data"]["vitals"]["original_filename"] == "report.pdf"

    record_id = json_data["data"]["id"]
    # Cleanup record
    client.delete(f"/api/records/{record_id}", headers=headers)


# 2. Successful PNG upload
def test_successful_png_upload(setup_data):
    headers = setup_data["headers"]
    patient_id = setup_data["patient_id"]

    png_bytes = b"\x89PNG\r\n\x1a\nFake PNG content..."
    files = {"file": ("xray.png", io.BytesIO(png_bytes), "image/png")}
    data = {"record_type": "Radiology"}

    res = client.post(
        f"/api/patients/{patient_id}/records/upload",
        headers=headers,
        files=files,
        data=data
    )

    assert res.status_code == 201
    json_data = res.json()
    assert json_data["data"]["record_type"] == "Radiology"

    record_id = json_data["data"]["id"]
    client.delete(f"/api/records/{record_id}", headers=headers)


# 3. Unauthenticated upload (401)
def test_unauthenticated_upload(setup_data):
    patient_id = setup_data["patient_id"]
    pdf_bytes = b"%PDF-1.4 Unauthenticated..."
    files = {"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    res = client.post(f"/api/patients/{patient_id}/records/upload", files=files)
    assert res.status_code == 401


# 4. Nonexistent patient upload (404)
def test_nonexistent_patient_upload(setup_data):
    headers = setup_data["headers"]
    pdf_bytes = b"%PDF-1.4 Nonexistent..."
    files = {"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    res = client.post(
        "/api/patients/999999/records/upload",
        headers=headers,
        files=files
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


# 5. Invalid file type upload (400)
def test_invalid_file_type_upload(setup_data):
    headers = setup_data["headers"]
    patient_id = setup_data["patient_id"]

    exe_bytes = b"MZ Executable file..."
    files = {"file": ("malicious.exe", io.BytesIO(exe_bytes), "application/x-msdownload")}

    res = client.post(
        f"/api/patients/{patient_id}/records/upload",
        headers=headers,
        files=files
    )
    assert res.status_code == 400
    assert "Unsupported file extension" in res.json()["detail"]


# 6. Oversized file upload (400)
def test_oversized_file_upload(setup_data):
    headers = setup_data["headers"]
    patient_id = setup_data["patient_id"]

    # 11 MB dummy content (> 10MB limit)
    large_bytes = b"0" * (11 * 1024 * 1024)
    files = {"file": ("large_scan.pdf", io.BytesIO(large_bytes), "application/pdf")}

    res = client.post(
        f"/api/patients/{patient_id}/records/upload",
        headers=headers,
        files=files
    )
    assert res.status_code == 400
    assert "exceeds maximum allowed limit" in res.json()["detail"]


# 7. Database record creation & retrieval
def test_get_patient_records_list(setup_data):
    headers = setup_data["headers"]
    patient_id = setup_data["patient_id"]

    pdf1 = b"%PDF-1.4 Doc 1"
    pdf2 = b"%PDF-1.4 Doc 2"

    r1 = client.post(f"/api/patients/{patient_id}/records/upload", headers=headers, files={"file": ("doc1.pdf", io.BytesIO(pdf1), "application/pdf")})
    r2 = client.post(f"/api/patients/{patient_id}/records/upload", headers=headers, files={"file": ("doc2.pdf", io.BytesIO(pdf2), "application/pdf")})

    list_res = client.get(f"/api/patients/{patient_id}/records", headers=headers)
    assert list_res.status_code == 200
    json_data = list_res.json()
    assert json_data["count"] >= 2

    # Cleanup records
    rec1_id = r1.json()["data"]["id"]
    rec2_id = r2.json()["data"]["id"]
    client.delete(f"/api/records/{rec1_id}", headers=headers)
    client.delete(f"/api/records/{rec2_id}", headers=headers)
