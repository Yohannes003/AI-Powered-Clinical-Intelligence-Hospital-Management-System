"""
ICU Patient Simulator
Generates realistic vital signs for simulated patients and streams them via WebSocket.
Simulates various clinical scenarios including cardiac events, respiratory distress,
sepsis, and neurological deterioration.
"""

import os
import sys
import json
import asyncio
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Patient, VitalSign, Alert
from app.risk_engine import risk_engine
from app.websocket_manager import manager

logger = logging.getLogger(__name__)

# Clinical scenarios for simulation
SCENARIOS = {
    "normal": {
        "heart_rate": (60, 100),
        "blood_pressure_systolic": (110, 140),
        "blood_pressure_diastolic": (70, 90),
        "respiratory_rate": (12, 20),
        "spo2": (95, 100),
        "temperature": (36.3, 37.5),
        "gcs_score": (14, 15),
    },
    "cardiac_distress": {
        "heart_rate": (120, 160),
        "blood_pressure_systolic": (80, 100),
        "blood_pressure_diastolic": (50, 70),
        "respiratory_rate": (22, 35),
        "spo2": (88, 95),
        "temperature": (36.5, 38.0),
        "gcs_score": (12, 15),
    },
    "respiratory_failure": {
        "heart_rate": (90, 130),
        "blood_pressure_systolic": (100, 140),
        "blood_pressure_diastolic": (65, 85),
        "respiratory_rate": (28, 45),
        "spo2": (78, 90),
        "temperature": (36.5, 38.5),
        "gcs_score": (10, 15),
    },
    "septic_shock": {
        "heart_rate": (110, 150),
        "blood_pressure_systolic": (60, 90),
        "blood_pressure_diastolic": (40, 60),
        "respiratory_rate": (24, 40),
        "spo2": (85, 95),
        "temperature": (38.5, 41.0),
        "gcs_score": (8, 14),
    },
    "neurological_decline": {
        "heart_rate": (50, 90),
        "blood_pressure_systolic": (120, 180),
        "blood_pressure_diastolic": (70, 100),
        "respiratory_rate": (8, 18),
        "spo2": (92, 98),
        "temperature": (36.0, 38.0),
        "gcs_score": (3, 10),
    },
    "recovering": {
        "heart_rate": (65, 95),
        "blood_pressure_systolic": (115, 145),
        "blood_pressure_diastolic": (72, 88),
        "respiratory_rate": (14, 22),
        "spo2": (93, 99),
        "temperature": (36.5, 37.8),
        "gcs_score": (13, 15),
    }
}


class PatientSimulator:
    """Simulates vital signs for a single patient."""

    def __init__(self, patient_id: int, patient_name: str, bed_number: str,
                 age: int = 65, base_scenario: str = "normal"):
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.bed_number = bed_number
        self.age = age
        self.base_scenario = base_scenario
        self.current_scenario = base_scenario
        self.scenario_timer = 0
        self.scenario_duration = random.randint(8, 18)
        self.vital_history = []
        self.trend_direction = 0

    def _add_noise(self, value, noise_percent=0.08):
        """Add realistic measurement noise."""
        if value is None:
            return None
        noise = value * noise_percent * (2 * random.random() - 1)
        return round(value + noise, 1)

    def _get_scenario_vitals(self):
        """Generate vitals based on current scenario."""
        scenario = SCENARIOS.get(self.current_scenario, SCENARIOS["normal"])

        vitals = {
            "heart_rate": random.randint(*scenario["heart_rate"]),
            "blood_pressure_systolic": random.randint(*scenario["blood_pressure_systolic"]),
            "blood_pressure_diastolic": random.randint(*scenario["blood_pressure_diastolic"]),
            "respiratory_rate": random.randint(*scenario["respiratory_rate"]),
            "spo2": round(random.uniform(*scenario["spo2"]), 1),
            "temperature": round(random.uniform(*scenario["temperature"]), 1),
            "gcs_score": random.randint(*scenario["gcs_score"]),
        }

        # Calculate MAP
        vitals["mean_arterial_pressure"] = round(
            vitals["blood_pressure_diastolic"] +
            (vitals["blood_pressure_systolic"] - vitals["blood_pressure_diastolic"]) / 3, 1
        )

        # Add noise for realism
        for key in vitals:
            vitals[key] = self._add_noise(vitals[key])

        if "gcs_score" in vitals and vitals["gcs_score"] is not None:
            vitals["gcs_score"] = max(3, min(15, int(round(vitals["gcs_score"]))))
        if "spo2" in vitals and vitals["spo2"] is not None:
            vitals["spo2"] = max(0, min(100, vitals["spo2"]))
        if "heart_rate" in vitals and vitals["heart_rate"] is not None:
            vitals["heart_rate"] = max(0, min(300, vitals["heart_rate"]))
        if "blood_pressure_systolic" in vitals and vitals["blood_pressure_systolic"] is not None:
            vitals["blood_pressure_systolic"] = max(0, min(300, vitals["blood_pressure_systolic"]))
        if "blood_pressure_diastolic" in vitals and vitals["blood_pressure_diastolic"] is not None:
            vitals["blood_pressure_diastolic"] = max(0, min(200, vitals["blood_pressure_diastolic"]))
        if "respiratory_rate" in vitals and vitals["respiratory_rate"] is not None:
            vitals["respiratory_rate"] = max(0, min(100, vitals["respiratory_rate"]))
        if "temperature" in vitals and vitals["temperature"] is not None:
            vitals["temperature"] = round(max(30, min(43, vitals["temperature"])), 1)
        if "pain_score" in vitals and vitals["pain_score"] is not None:
            vitals["pain_score"] = max(0, min(10, int(round(vitals["pain_score"]))))
        if "mean_arterial_pressure" in vitals and vitals["mean_arterial_pressure"] is not None:
            vitals["mean_arterial_pressure"] = max(0, min(200, vitals["mean_arterial_pressure"]))
        if "central_venous_pressure" in vitals and vitals["central_venous_pressure"] is not None:
            vitals["central_venous_pressure"] = max(0, min(30, vitals["central_venous_pressure"]))

        vitals["blood_pressure_diastolic"] = min(
            vitals["blood_pressure_diastolic"],
            vitals["blood_pressure_systolic"] - 20
        )

        return vitals

    def update_scenario(self):
        self.scenario_timer += 1

        if self.scenario_timer >= self.scenario_duration:
            self.scenario_timer = 0
            self.scenario_duration = random.randint(6, 14)

            all_crisis = ["cardiac_distress", "respiratory_failure", "septic_shock", "neurological_decline"]
            transitions = {
                "normal":                all_crisis + ["recovering", "normal"],
                "cardiac_distress":      all_crisis + ["recovering"],
                "respiratory_failure":   all_crisis + ["recovering"],
                "septic_shock":          all_crisis + ["recovering"],
                "neurological_decline":  all_crisis + ["recovering"],
                "recovering":            ["recovering", "normal"] + all_crisis,
            }

            choices = transitions.get(self.current_scenario, all_crisis + ["normal"])
            self.current_scenario = random.choice(choices)

    def generate_vitals(self) -> Dict:
        """Generate a new set of vital signs."""
        self.update_scenario()
        vitals = self._get_scenario_vitals()

        # Calculate risk
        risk_result = risk_engine.predict(vitals, self.age)
        vitals["risk_score"] = risk_result["risk_score"]
        vitals["risk_level"] = risk_result["risk_level"]

        # Check for alerts
        alert_data = risk_engine.check_alert_thresholds(vitals, self.patient_name)

        return {
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "bed_number": self.bed_number,
            "timestamp": datetime.now().isoformat(),
            **vitals,
            "alert_triggered": alert_data is not None,
            "alert_data": alert_data,
            "scenario": self.current_scenario
        }


class ICUSimulator:
    """Main ICU simulator managing multiple patient simulators."""

    def __init__(self, num_patients: int = 8, interval: float = 2.0):
        self.num_patients = num_patients
        self.interval = interval  # seconds between readings
        self.simulators: List[PatientSimulator] = []
        self.running = False
        self.tasks = []

    def _get_or_create_patients(self, db: Session) -> List[Patient]:
        """Get existing patients or create demo patients."""
        patients = db.query(Patient).filter(Patient.is_active.is_(True)).all()

        if not patients:
            logger.info("Creating demo patients...")
            demo_data = [
                {"name": "John Smith", "age": 72, "gender": "male", "bed_number": "ICU-101",
                 "diagnosis": "Post-CABG, acute kidney injury"},
                {"name": "Maria Garcia", "age": 58, "gender": "female", "bed_number": "ICU-102",
                 "diagnosis": "Severe pneumonia, ARDS"},
                {"name": "Robert Chen", "age": 45, "gender": "male", "bed_number": "ICU-103",
                 "diagnosis": "Traumatic brain injury"},
                {"name": "Sarah Johnson", "age": 67, "gender": "female", "bed_number": "ICU-104",
                 "diagnosis": "Sepsis, multiple organ dysfunction"},
                {"name": "David Williams", "age": 81, "gender": "male", "bed_number": "ICU-105",
                 "diagnosis": "Acute decompensated heart failure"},
                {"name": "Emily Brown", "age": 52, "gender": "female", "bed_number": "ICU-106",
                 "diagnosis": "Subarachnoid hemorrhage"},
                {"name": "Michael Davis", "age": 39, "gender": "male", "bed_number": "ICU-107",
                 "diagnosis": "Drug overdose, respiratory failure"},
                {"name": "Lisa Wilson", "age": 74, "gender": "female", "bed_number": "ICU-108",
                 "diagnosis": "GI bleeding, hemodynamic instability"},
            ]

            for data in demo_data:
                patient = Patient(**data)
                db.add(patient)

            db.commit()
            patients = db.query(Patient).filter(Patient.is_active.is_(True)).all()

        return patients

    def _assign_scenarios(self, patients: List[Patient]) -> Dict[int, str]:
        scenarios = ["cardiac_distress", "respiratory_failure", "septic_shock",
                     "neurological_decline", "recovering", "normal",
                     "cardiac_distress", "respiratory_failure"]
        return {p.id: scenarios[i % len(scenarios)] for i, p in enumerate(patients)}

    async def _save_vitals(self, vital_data: Dict):
        """Save vitals to database and create alerts if needed."""
        try:
            db = SessionLocal()

            # Create vital sign record
            vital = VitalSign(
                patient_id=vital_data["patient_id"],
                heart_rate=vital_data.get("heart_rate"),
                blood_pressure_systolic=vital_data.get("blood_pressure_systolic"),
                blood_pressure_diastolic=vital_data.get("blood_pressure_diastolic"),
                mean_arterial_pressure=vital_data.get("mean_arterial_pressure"),
                respiratory_rate=vital_data.get("respiratory_rate"),
                spo2=vital_data.get("spo2"),
                temperature=vital_data.get("temperature"),
                gcs_score=vital_data.get("gcs_score"),
                risk_score=vital_data.get("risk_score", 0),
                risk_level=vital_data.get("risk_level", "low")
            )
            db.add(vital)

            # Update patient risk score
            patient = db.query(Patient).filter(Patient.id == vital_data["patient_id"]).first()
            if patient:
                patient.risk_score = vital_data.get("risk_score", 0)
                if vital_data.get("risk_level") in ("critical", "moderate"):
                    patient.status = "critical"
                else:
                    patient.status = "stable"

            # Create alert if triggered
            if vital_data.get("alert_triggered") and vital_data.get("alert_data"):
                alert_data = vital_data["alert_data"]
                alert = Alert(
                    patient_id=vital_data["patient_id"],
                    alert_type=alert_data["alert_type"],
                    severity=alert_data["severity"],
                    message=alert_data["message"],
                    vital_sign_snapshot=alert_data.get("vital_sign_snapshot")
                )
                db.add(alert)

            db.commit()
            db.close()

        except Exception as e:
            logger.error(f"Error saving vitals: {e}")

    async def _stream_vitals(self, simulator: PatientSimulator):
        """Stream vitals for a single patient."""
        while self.running:
            try:
                # Generate vitals
                vital_data = simulator.generate_vitals()

                # Save to database
                await self._save_vitals(vital_data)

                # Broadcast via WebSocket (wrapped in try to not break on no connections)
                try:
                    ws_data = {
                        "patient_id": vital_data["patient_id"],
                        "patient_name": vital_data["patient_name"],
                        "bed_number": vital_data["bed_number"],
                        "timestamp": vital_data["timestamp"],
                        "heart_rate": vital_data.get("heart_rate"),
                        "blood_pressure_systolic": vital_data.get("blood_pressure_systolic"),
                        "blood_pressure_diastolic": vital_data.get("blood_pressure_diastolic"),
                        "respiratory_rate": vital_data.get("respiratory_rate"),
                        "spo2": vital_data.get("spo2"),
                        "temperature": vital_data.get("temperature"),
                        "gcs_score": vital_data.get("gcs_score"),
                        "risk_score": vital_data.get("risk_score"),
                        "risk_level": vital_data.get("risk_level"),
                        "alert_triggered": vital_data.get("alert_triggered", False),
                        "alert_message": vital_data["alert_data"]["message"] if vital_data.get("alert_data") else None,
                    }
                    await manager.broadcast_vital_update(ws_data)

                    # Broadcast alert separately if triggered
                    if vital_data.get("alert_triggered") and vital_data.get("alert_data"):
                        await manager.broadcast_alert({
                            "patient_id": vital_data["patient_id"],
                            "patient_name": vital_data["patient_name"],
                            "bed_number": vital_data["bed_number"],
                            **vital_data["alert_data"]
                        })

                except Exception as e:
                    # WebSocket errors shouldn't stop the simulator
                    pass

                # Wait for next reading
                await asyncio.sleep(self.interval)

            except Exception as e:
                logger.error(f"Error in vital stream for patient {simulator.patient_id}: {e}")
                await asyncio.sleep(self.interval)

    async def start(self):
        """Start the ICU simulator."""
        logger.info("=" * 60)
        logger.info("Starting ICU Simulator")
        logger.info("=" * 60)

        self.running = True

        # Get patients from database
        db = SessionLocal()
        patients = self._get_or_create_patients(db)
        scenarios = self._assign_scenarios(patients)
        db.close()

        logger.info(f"Monitoring {len(patients)} patients")

        # Create simulators for each patient
        for patient in patients:
            simulator = PatientSimulator(
                patient_id=patient.id,
                patient_name=patient.name,
                bed_number=patient.bed_number,
                age=patient.age,
                base_scenario=scenarios.get(patient.id, "normal")
            )
            self.simulators.append(simulator)

        # Start streaming tasks
        self.tasks = [
            asyncio.create_task(self._stream_vitals(sim))
            for sim in self.simulators
        ]

        logger.info("ICU Simulator is running")
        logger.info(f"Update interval: {self.interval} seconds")

        # Keep running
        try:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info("Simulator tasks cancelled")

    async def stop(self):
        """Stop the ICU simulator."""
        logger.info("Stopping ICU Simulator...")
        self.running = False

        for task in self.tasks:
            task.cancel()

        self.tasks = []
        self.simulators = []
        logger.info("ICU Simulator stopped")


# Global simulator instance
_simulator: Optional[ICUSimulator] = None


def get_simulator() -> ICUSimulator:
    """Get or create the global simulator instance."""
    global _simulator
    if _simulator is None:
        _simulator = ICUSimulator(num_patients=8, interval=2.0)
    return _simulator


async def start_simulator():
    """Start the simulator as a background task."""
    simulator = get_simulator()
    asyncio.create_task(simulator.start())


async def stop_simulator():
    """Stop the simulator."""
    global _simulator
    if _simulator:
        await _simulator.stop()
        _simulator = None


# Run standalone
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    async def main():
        simulator = ICUSimulator(num_patients=8, interval=2.0)

        try:
            await simulator.start()
        except KeyboardInterrupt:
            await simulator.stop()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
