# AI-Powered Real-Time ICU Monitoring and Clinical Decision Support System

A comprehensive full-stack application for real-time ICU patient monitoring with AI-powered risk prediction, clinical alerts, and automated report generation.

## Features

- **Real-Time Vital Streaming** - WebSocket-based live vital signs from simulated patients
- **XGBoost Risk Prediction** - ML model predicts patient deterioration risk
- **Clinical Alert Engine** - Automated alerts for critical vital sign thresholds
- **AI-Generated Reports** - Automated clinical summary reports with recommendations
- **Interactive Dashboard** - React-based real-time monitoring dashboard with charts
- **Patient Management** - Full CRUD for ICU patients
- **Docker Support** - Complete containerization with docker-compose

## Architecture

```
hospital-ai-system/
|
|-- backend/                 # FastAPI Backend
|   |-- app/
|   |   |-- main.py          # FastAPI app entry
|   |   |-- database.py      # PostgreSQL connection
|   |   |-- models.py        # SQLAlchemy models
|   |   |-- schemas.py       # Pydantic schemas
|   |   |-- websocket_manager.py  # WebSocket handler
|   |   |-- risk_engine.py   # XGBoost risk prediction
|   |   |-- routes/
|   |   |   |-- patients.py  # Patient CRUD API
|   |   |   |-- vitals.py    # Vitals & dashboard API
|   |   |   |-- reports.py   # AI report generation
|   |   |-- ml/
|   |   |   |-- train_model.py   # Model training
|   |   |   |-- heart_model.pkl  # Trained model
|   |-- simulator/
|   |   |-- icu_simulator.py     # Patient data simulator
|   |-- requirements.txt
|   |-- Dockerfile
|
|-- frontend/                # React Frontend
|   |-- src/
|   |   |-- App.jsx
|   |   |-- pages/
|   |   |   |-- Dashboard.jsx
|   |   |-- components/
|   |   |   |-- PatientCard.jsx
|   |   |   |-- VitalChart.jsx
|   |   |   |-- AlertPanel.jsx
|   |   |-- services/
|   |   |   |-- websocket.js
|   |-- package.json
|   |-- vite.config.js
|   |-- Dockerfile
|
|-- docker-compose.yml
|-- .env
|-- README.md
```

## VS Code Setup Commands

### Prerequisites

1. Install **VS Code** with extensions:
   - Python
   - ESLint
   - Prettier
   - Docker (optional)

2. Install system requirements:
   - **Python 3.11+**
   - **Node.js 20+**
   - **PostgreSQL 16** (or use Docker)
   - **Docker & Docker Compose** (optional)

### Option 1: Docker (Recommended - Full Stack)

```bash
# Open project in VS Code
# Terminal > New Terminal

# Build and start all services
docker-compose up --build

# Access the application:
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# API Docs:  http://localhost:8000/docs

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Stop and remove volumes (reset database)
docker-compose down -v
```

### Option 2: Local Development (VS Code Terminal)

#### Step 1: Start PostgreSQL

```bash
# Using Docker for PostgreSQL
docker run -d --name icu-postgres \
  -e POSTGRES_USER=icu_user \
  -e POSTGRES_PASSWORD=icu_password \
  -e POSTGRES_DB=icu_monitoring \
  -p 5432:5432 \
  postgres:16-alpine

# Or use local PostgreSQL - create database:
# psql -U postgres
# CREATE DATABASE icu_monitoring;
# CREATE USER icu_user WITH PASSWORD 'icu_password';
# GRANT ALL PRIVILEGES ON DATABASE icu_monitoring TO icu_user;
```

#### Step 2: Setup Backend

```bash
# In VS Code terminal, navigate to backend
cd hospital-ai-system/backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Train the ML model
python -m app.ml.train_model

# Start the FastAPI server (includes simulator)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# API will be available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

#### Step 3: Setup Frontend (New Terminal)

```bash
# Open a new VS Code terminal
cd hospital-ai-system/frontend

# Install dependencies
npm install

# Start the development server
npm run dev

# Frontend will be available at http://localhost:5173
```

### Option 3: VS Code Run Configurations

Create `.vscode/launch.json` in the project root:

```json
{
  "version": "0.2.0",
  "compounds": [
    {
      "name": "Full Stack",
      "configurations": ["Backend", "Frontend"]
    }
  ],
  "configurations": [
    {
      "name": "Backend",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "jinja": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}/backend",
        "DATABASE_URL": "postgresql://icu_user:icu_password@localhost:5432/icu_monitoring"
      }
    },
    {
      "name": "Frontend",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "dev"],
      "cwd": "${workspaceFolder}/frontend"
    }
  ]
}
```

Press `F5` to start debugging, or use the Run panel in VS Code.

## API Endpoints

### Patients
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/patients/` | List all patients |
| POST | `/patients/` | Create patient |
| GET | `/patients/{id}` | Get patient |
| PUT | `/patients/{id}` | Update patient |
| DELETE | `/patients/{id}` | Discharge patient |
| GET | `/patients/{id}/stats` | Patient statistics |

### Vitals & Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/vitals/{patient_id}` | Vital history |
| GET | `/vitals/{patient_id}/latest` | Latest vitals |
| GET | `/dashboard/stats` | Dashboard stats |
| GET | `/dashboard/risk-distribution` | Risk distribution |
| WS | `/ws/dashboard` | Dashboard WebSocket |
| WS | `/ws/patient/{id}` | Patient WebSocket |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/reports/generate` | Generate AI report |
| GET | `/reports/patient/{id}` | Patient reports |
| GET | `/reports/{id}` | Get report |

## WebSocket Protocol

Connect to `ws://localhost:8000/ws/dashboard` for real-time updates.

**Incoming messages:**
- `vital_update` - New vital signs for any patient
- `alert` - Clinical alert triggered
- `patient_update` - Patient status change
- `connected` - Connection confirmation

**Outgoing actions:**
- `{"action": "ping"}` - Keep connection alive
- `{"action": "stats"}` - Get connection statistics

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql://... | PostgreSQL connection |
| `API_PORT` | 8000 | Backend port |
| `VITE_API_URL` | http://localhost:8000 | Backend URL (frontend) |
| `VITE_WS_URL` | ws://localhost:8000 | WebSocket URL (frontend) |

## ML Model

The risk prediction model uses XGBoost trained on synthetic clinical data:

**Features:**
- Age, Heart Rate, Blood Pressure, Respiratory Rate
- SpO2, Temperature, GCS Score

**Output:** Risk score (0-1) with levels: low, medium, high, critical

To retrain:
```bash
cd backend
python -m app.ml.train_model
```

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, WebSocket
- **ML**: XGBoost, scikit-learn, NumPy, Pandas
- **Frontend**: React, Vite, Tailwind CSS, Recharts, Lucide Icons
- **Infrastructure**: Docker, Docker Compose, Uvicorn

## License

MIT
