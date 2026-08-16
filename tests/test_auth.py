import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.database.connection import SessionLocal
from app.models.user import User
from app.core.security import verify_password

client = TestClient(app)


def get_auth_headers(email: str = "auth_test_user@hospital.org", password: str = "testpassword123"):
    """Helper function to register/login and return Bearer auth headers."""
    client.post(
        "/api/auth/register",
        json={
            "name": "Auth Test User",
            "email": email,
            "password": password
        }
    )
    login_res = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password
        }
    )
    token = login_res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. Successful registration
def test_successful_registration():
    reg_res = client.post(
        "/api/auth/register",
        json={
            "name": "Doctor Alice",
            "email": "alice@hospital.org",
            "password": "securepassword123"
        }
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == "alice@hospital.org"
    assert user_data["name"] == "Doctor Alice"
    assert "hashed_password" not in user_data
    assert "password" not in user_data

    # Cleanup DB
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == "alice@hospital.org")).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 2. Duplicate email (409)
def test_duplicate_email_registration():
    headers = get_auth_headers("dup_test@hospital.org", "password123")

    dup_res = client.post(
        "/api/auth/register",
        json={
            "name": "Duplicate User",
            "email": "dup_test@hospital.org",
            "password": "password123"
        }
    )
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.json()["detail"]

    # Cleanup
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == "dup_test@hospital.org")).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 3. Invalid email (422)
def test_invalid_email_registration():
    res = client.post(
        "/api/auth/register",
        json={
            "name": "Invalid Email User",
            "email": "not-an-email",
            "password": "password123"
        }
    )
    assert res.status_code == 422


# 4. Successful login
def test_successful_login():
    get_auth_headers("login_test@hospital.org", "password123")

    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "login_test@hospital.org",
            "password": "password123"
        }
    )
    assert login_res.status_code == 200
    json_data = login_res.json()
    assert json_data["success"] is True
    assert "access_token" in json_data["data"]
    assert json_data["data"]["token_type"] == "bearer"

    # Cleanup
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == "login_test@hospital.org")).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 5. Wrong password (401)
def test_wrong_password_login():
    get_auth_headers("wrong_pw@hospital.org", "correctpassword")

    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "wrong_pw@hospital.org",
            "password": "wrongpassword"
        }
    )
    assert login_res.status_code == 401
    assert "Invalid email or password" in login_res.json()["detail"]

    # Cleanup
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == "wrong_pw@hospital.org")).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 6. Non-existent user login (401)
def test_nonexistent_user_login():
    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent@hospital.org",
            "password": "password123"
        }
    )
    assert login_res.status_code == 401
    assert "Invalid email or password" in login_res.json()["detail"]


# 7. JWT returned successfully
def test_jwt_structure():
    headers = get_auth_headers("jwt_struct@hospital.org", "password123")
    token = headers["Authorization"].split(" ")[1]
    assert len(token) > 20
    assert token.count(".") == 2  # Standard JWT format: header.payload.signature

    # Cleanup
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == "jwt_struct@hospital.org")).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 8. GET /api/auth/me with valid token (200)
def test_get_me_valid_token():
    headers = get_auth_headers("get_me@hospital.org", "password123")

    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    json_data = me_res.json()
    assert json_data["success"] is True
    assert json_data["data"]["email"] == "get_me@hospital.org"

    # Cleanup
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == "get_me@hospital.org")).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 9. GET /api/auth/me without token (401)
def test_get_me_without_token():
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 401


# 10. GET /api/auth/me with invalid token (401)
def test_get_me_invalid_token():
    me_res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert me_res.status_code == 401


# 11. Protected patient endpoint without token (401)
def test_protected_patient_endpoint_without_token():
    res = client.get("/api/patients")
    assert res.status_code == 401


# 12. Protected patient endpoint with valid token (200)
def test_protected_patient_endpoint_with_valid_token():
    headers = get_auth_headers("prot_pat@hospital.org", "password123")

    res = client.get("/api/patients", headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Cleanup
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == "prot_pat@hospital.org")).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()


# 13. Verify password is stored hashed in DB
def test_password_stored_hashed():
    email = "hashed_db_check@hospital.org"
    raw_password = "mysecretpassword123"
    headers = get_auth_headers(email, raw_password)

    db = SessionLocal()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    assert user is not None
    assert user.hashed_password != raw_password
    assert verify_password(raw_password, user.hashed_password) is True

    # Cleanup
    db.delete(user)
    db.commit()
    db.close()


# 14. Verify hashed_password is never returned in API responses
def test_hashed_password_never_returned():
    email = "never_returned@hospital.org"
    headers = get_auth_headers(email, "password123")

    me_res = client.get("/api/auth/me", headers=headers)
    response_str = me_res.text
    assert "hashed_password" not in response_str

    # Cleanup
    db = SessionLocal()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user:
        db.delete(user)
        db.commit()
    db.close()
