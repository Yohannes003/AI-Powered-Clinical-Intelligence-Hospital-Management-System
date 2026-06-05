"""
Main FastAPI application for the ICU Monitoring System.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import warnings

# Suppress noisy sklearn warning about feature names in container logs
warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names, but StandardScaler was fitted with feature names",
)

from app.database import init_db
from app.routes import patients, vitals, reports
from app.websocket_manager import manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global simulator task
_simulator_task = None


async def start_background_simulator():
    """Start the ICU simulator in the background."""
    try:
        from simulator.icu_simulator import ICUSimulator
        simulator = ICUSimulator(num_patients=8, interval=2.0)
        await simulator.start()
    except Exception as e:
        logger.error(f"Simulator error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("ICU Monitoring System Starting...")
    logger.info("=" * 60)

    # Initialize database tables
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        logger.info("Application will retry on first request")

    # Seed demo data if no patients exist
    try:
        from app.database import SessionLocal
        from app.models import Patient
        db = SessionLocal()
        patient_count = db.query(Patient).count()
        if patient_count == 0:
            logger.info("No patients found - seeding demo data...")
            seed_demo_data(db)
        db.close()
    except Exception as e:
        logger.error(f"Demo data seeding error: {e}")

    # Start background simulator
    global _simulator_task
    logger.info("Starting ICU simulator...")
    _simulator_task = asyncio.create_task(start_background_simulator())

    logger.info("ICU Monitoring System is ready!")
    yield

    # Shutdown
    logger.info("ICU Monitoring System shutting down...")
    if _simulator_task:
        _simulator_task.cancel()
        try:
            await _simulator_task
        except asyncio.CancelledError:
            pass


def seed_demo_data(db):
    """Seed the database with demo patients."""
    from app.models import Patient

    demo_patients = [
        Patient(name="John Smith", age=72, gender="male", bed_number="ICU-101",
                diagnosis="Post-CABG, acute kidney injury", status="critical", risk_score=0.75),
        Patient(name="Maria Garcia", age=58, gender="female", bed_number="ICU-102",
                diagnosis="Severe pneumonia, ARDS", status="critical", risk_score=0.82),
        Patient(name="Robert Chen", age=45, gender="male", bed_number="ICU-103",
                diagnosis="Traumatic brain injury", status="stable", risk_score=0.35),
        Patient(name="Sarah Johnson", age=67, gender="female", bed_number="ICU-104",
                diagnosis="Sepsis, multiple organ dysfunction", status="critical", risk_score=0.91),
        Patient(name="David Williams", age=81, gender="male", bed_number="ICU-105",
                diagnosis="Acute decompensated heart failure", status="stable", risk_score=0.42),
        Patient(name="Emily Brown", age=52, gender="female", bed_number="ICU-106",
                diagnosis="Subarachnoid hemorrhage", status="critical", risk_score=0.68),
        Patient(name="Michael Davis", age=39, gender="male", bed_number="ICU-107",
                diagnosis="Drug overdose, respiratory failure", status="stable", risk_score=0.28),
        Patient(name="Lisa Wilson", age=74, gender="female", bed_number="ICU-108",
                diagnosis="GI bleeding, hemodynamic instability", status="critical", risk_score=0.79),
    ]

    for patient in demo_patients:
        db.add(patient)

    db.commit()
    logger.info(f"Seeded {len(demo_patients)} demo patients")


# Create FastAPI app
app = FastAPI(
    title="ICU Monitoring System API",
    description="AI-Powered Real-Time ICU Monitoring and Clinical Decision Support System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(patients.router)
app.include_router(vitals.router)
app.include_router(reports.router)


@app.get("/")
def root():
    """API root endpoint."""
    return {
        "message": "ICU Monitoring System API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "patients": "/patients",
            "vitals": "/vitals",
            "reports": "/reports",
            "dashboard": "/dashboard/stats",
            "websocket_dashboard": "/ws/dashboard",
            "websocket_patient": "/ws/patient/{patient_id}"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "version": "1.0.0"
    }
