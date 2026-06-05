# 🏥 CIOS v6 — Clinical Intelligence Operating System

AI-native hospital ERP with real-time decision support, RBAC, clinical messaging, and specialist referrals.

---

## Quick Start (Windows / Mac / Linux)

### Prerequisites
- Python 3.10 – 3.14
- Node.js 18+
- VS Code (recommended)

### 1. Backend — Terminal 1

```powershell
cd backend

# Create & activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux

# Upgrade pip first (prevents build errors)
python -m pip install --upgrade pip

# Install packages (pure Python — no compiler needed)
pip install -r requirements.txt

# Copy environment file
copy .env.example .env         # Windows
# cp .env.example .env         # Mac / Linux

# Start server
python -m uvicorn app.main:app --reload --port 8000
```

You should see:
```
✅ Database initialized
✅ Default users seeded
✅ Event bus started
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 2. Seed Demo Data — Terminal 2 (optional but recommended)

```powershell
cd backend
venv\Scripts\activate
python ..\scripts\seed_demo.py    # Windows
# python ../scripts/seed_demo.py  # Mac / Linux
```

### 3. Frontend — Terminal 3

```powershell
cd frontend
npm install
npm start
```

Opens automatically at **http://localhost:3000**

---

## Login Credentials

| Role   | Email                     | Password    |
|--------|---------------------------|-------------|
| Admin  | admin@cios.hospital       | Admin@123   |
| Doctor | doctor@cios.hospital      | Doctor@123  |
| Nurse  | nurse@cios.hospital       | Nurse@123   |

---

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc
- Health:      http://localhost:8000/health

---

## Feature Overview

### 🧠 AI Engine
- Risk prediction (0–1 score) with XAI explanation
- Anomaly detection on vitals and labs
- Clinical Digital Twin — 72h trajectory + what-if scenarios
- LLM clinical summaries (Anthropic API, optional)

### 💬 Clinical Messaging
- Secure staff-to-staff conversations
- Patient-contextual threads
- Unread badges + auto-polling
- Urgent message flagging

### 📋 Referral System
- Create referrals with priority (STAT / URGENT / ROUTINE)
- Full workflow: pending → accepted → consultation notes → completed
- AI risk snapshot attached at referral time
- Specialist consultation notes with medications + follow-up

### 👑 RBAC + Admin Panel
- 5 roles: Admin, Doctor, Nurse, Lab Tech, Viewer
- 28+ named permissions
- Approval desk — new signups pending admin review
- Role editor, activate/deactivate accounts
- Full permissions matrix

### 📊 Reporting
- PDF (ReportLab), CSV, Excel (OpenPyXL), XPS
- AI summary embedded in every report
- Token-authenticated download links

### 🔒 Security & Compliance
- JWT auth (Python 3.14 compatible — no passlib)
- Immutable HIPAA-ready audit trail
- Role-based endpoint guards
- Event-driven architecture (Kafka-ready)

---

## Database

Default: **SQLite** (no install needed)  
Production: set `DATABASE_URL=postgresql://...` in `.env`

20 tables:
`users`, `patients`, `visits`, `diagnoses`, `vital_signs`, `lab_results`,
`ai_predictions`, `clinical_digital_twins`, `clinical_alerts`, `audit_logs`,
`domain_events`, `reports`, `conversations`, `conversation_participants`,
`messages`, `message_receipts`, `referrals`, `consultation_notes`

---

## Every Session After First Setup

```powershell
# Terminal 1 — Backend
cd backend && venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm start
```
