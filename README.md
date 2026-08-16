# FastAPI Backend — Clinical Decision Intelligence System

Senior Backend & Database Implementation (Member 2).

## Technology Stack
- **Python**: 3.10+
- **Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **Settings**: Pydantic Settings

## Project Structure
```text
backend-python/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entrypoint
│   └── core/
│       ├── __init__.py
│       └── config.py        # Pydantic environment configuration
├── tests/
│   ├── __init__.py
│   └── test_health.py       # Basic health & root route tests
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup & Running on Windows

### 1. Create & Activate Virtual Environment
Open PowerShell or Command Prompt in `backend-python`:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Create Environment File
```powershell
copy .env.example .env
```

### 4. Run Development Server (Port 8000)
```powershell
uvicorn app.main:app --reload --port 8000
```

### 5. Verify Endpoints
- **Root**: `http://localhost:8000/`
- **Health Check**: `http://localhost:8000/health` or `http://localhost:8000/api/health`
- **Swagger Interactive API Docs**: `http://localhost:8000/docs`

### 6. Run Unit Tests
```powershell
pytest
```
