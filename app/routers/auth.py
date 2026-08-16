from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, UserResponse
from app.core.security import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new healthcare user in PostgreSQL with a securely hashed password."
)
def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db)
):
    # Check for existing email
    existing_user = db.execute(
        select(User).where(User.email == user_in.email)
    ).scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists."
        )

    hashed_pw = hash_password(user_in.password)
    new_user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hashed_pw,
        role="user"
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction error during registration."
        )

    return UserResponse.model_validate(new_user)


@router.post(
    "/login",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticates user credentials and returns a signed JWT bearer token."
)
def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    user = db.execute(
        select(User).where(User.email == credentials.email)
    ).scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "token_type": "bearer"
        }
    }


@router.get(
    "/me",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns authenticated user profile details from Bearer JWT token."
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    return {
        "success": True,
        "data": UserResponse.model_validate(current_user)
    }
