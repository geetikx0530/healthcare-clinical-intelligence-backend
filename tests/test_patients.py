import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.database.connection import SessionLocal
from app.models.user import User

client = TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    email = "patient_test_doc@hospital.org"
    password = "docpassword123"
    client.post(
        "/api/auth/register",
        json={"name": "Dr. Patient Tester", "email": email, "password": password}
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password}
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    yield headers

    # Cleanup test user after module runs
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 1. Create patient
def test_create_patient(auth_headers):
    response = client.post(
        "/api/patients",
        headers=auth_headers,
        json={
            "patient_code": "PT-CRUD-1001",
            "name": "Sarah Connor",
            "age": 35,
            "gender": "Female",
            "hospital": "Metro Health",
            "doctor": "Dr. Silberman",
            "status": "Medium Risk",
            "risk_score": 45.0
        }
    )
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["data"]["patient_code"] == "PT-CRUD-1001"
    assert json_data["data"]["name"] == "Sarah Connor"
    patient_id = json_data["data"]["id"]

    # Cleanup
    client.delete(f"/api/patients/{patient_id}", headers=auth_headers)


# 2. Retrieve single patient
def test_get_patient_by_id(auth_headers):
    create_res = client.post(
        "/api/patients",
        headers=auth_headers,
        json={
            "patient_code": "PT-CRUD-1002",
            "name": "Kyle Reese",
            "age": 28
        }
    )
    patient_id = create_res.json()["data"]["id"]

    get_res = client.get(f"/api/patients/{patient_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["name"] == "Kyle Reese"

    # Cleanup
    client.delete(f"/api/patients/{patient_id}", headers=auth_headers)


# 3. Retrieve all patients
def test_get_all_patients(auth_headers):
    c1 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-ALL-01", "name": "Patient One"})
    c2 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-ALL-02", "name": "Patient Two"})

    res = client.get("/api/patients", headers=auth_headers)
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["success"] is True
    assert json_data["total"] >= 2
    assert "data" in json_data

    # Cleanup
    client.delete(f"/api/patients/{c1.json()['data']['id']}", headers=auth_headers)
    client.delete(f"/api/patients/{c2.json()['data']['id']}", headers=auth_headers)


# 4. Pagination
def test_patients_pagination(auth_headers):
    c1 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-PAG-01", "name": "Pag One"})
    c2 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-PAG-02", "name": "Pag Two"})

    res = client.get("/api/patients?page=1&limit=1", headers=auth_headers)
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["page"] == 1
    assert json_data["limit"] == 1
    assert len(json_data["data"]) == 1

    # Cleanup
    client.delete(f"/api/patients/{c1.json()['data']['id']}", headers=auth_headers)
    client.delete(f"/api/patients/{c2.json()['data']['id']}", headers=auth_headers)


# 5. Update patient
def test_update_patient(auth_headers):
    c = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-UPD-01", "name": "Original Name", "age": 40})
    patient_id = c.json()["data"]["id"]

    update_res = client.put(
        f"/api/patients/{patient_id}",
        headers=auth_headers,
        json={"name": "Updated Name", "status": "High Risk", "risk_score": 88.0}
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()["data"]
    assert updated_data["name"] == "Updated Name"
    assert updated_data["status"] == "High Risk"
    assert updated_data["risk_score"] == 88.0
    assert updated_data["age"] == 40  # Unchanged

    # Cleanup
    client.delete(f"/api/patients/{patient_id}", headers=auth_headers)


# 6. Delete patient
def test_delete_patient(auth_headers):
    c = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-DEL-01", "name": "Delete Me"})
    patient_id = c.json()["data"]["id"]

    del_res = client.delete(f"/api/patients/{patient_id}", headers=auth_headers)
    assert del_res.status_code == 200

    get_res = client.get(f"/api/patients/{patient_id}", headers=auth_headers)
    assert get_res.status_code == 404


# 7. Duplicate patient_code (409)
def test_duplicate_patient_code(auth_headers):
    c1 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-DUP-01", "name": "First Patient"})
    assert c1.status_code == 201

    c2 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-DUP-01", "name": "Second Patient"})
    assert c2.status_code == 409
    assert "already exists" in c2.json()["detail"]

    # Cleanup
    client.delete(f"/api/patients/{c1.json()['data']['id']}", headers=auth_headers)


# 8. Patient not found (404)
def test_patient_not_found(auth_headers):
    res = client.get("/api/patients/999999", headers=auth_headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


# 9. Invalid age (422)
def test_invalid_age_validation(auth_headers):
    res = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-INV-AGE", "name": "Bad Age", "age": 200})
    assert res.status_code == 422


# 10. Invalid risk_score (422)
def test_invalid_risk_score_validation(auth_headers):
    res = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-INV-SCORE", "name": "Bad Score", "risk_score": 150.0})
    assert res.status_code == 422


# 11. Search by patient name
def test_search_by_name(auth_headers):
    c1 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-SRCH-01", "name": "UniqueNameX", "hospital": "Alpha"})
    c2 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-SRCH-02", "name": "OtherNameY", "hospital": "Beta"})

    res = client.get("/api/patients/search?query=uniquenamex", headers=auth_headers)
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["count"] == 1
    assert json_data["data"][0]["name"] == "UniqueNameX"

    # Cleanup
    client.delete(f"/api/patients/{c1.json()['data']['id']}", headers=auth_headers)
    client.delete(f"/api/patients/{c2.json()['data']['id']}", headers=auth_headers)


# 12. Search by patient code
def test_search_by_code(auth_headers):
    c1 = client.post("/api/patients", headers=auth_headers, json={"patient_code": "PT-CODE-SEARCH-999", "name": "Code Search Test"})

    res = client.get("/api/patients/search?query=search-999", headers=auth_headers)
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["count"] == 1
    assert json_data["data"][0]["patient_code"] == "PT-CODE-SEARCH-999"

    # Cleanup
    client.delete(f"/api/patients/{c1.json()['data']['id']}", headers=auth_headers)
