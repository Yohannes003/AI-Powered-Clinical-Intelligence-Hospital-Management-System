#!/usr/bin/env python3
"""
CIOS Demo Data Seeder
Run: python scripts/seed_demo.py
Seeds realistic patient data for demonstration
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from datetime import datetime, timedelta
import random

DEMO_PATIENTS = [
    {
        "full_name": "Ahmad Hassan", "gender": "Male", "blood_type": "O+",
        "date_of_birth": "1965-03-14", "ward": "Cardiology", "bed_number": "C-12",
        "allergies": ["Penicillin"], "chronic_conditions": ["Hypertension", "Type 2 Diabetes"],
        "current_medications": ["Metformin 500mg", "Lisinopril 10mg"], "status": "active",
        "contact_phone": "+92-300-1234567",
    },
    {
        "full_name": "Sara Khan", "gender": "Female", "blood_type": "A-",
        "date_of_birth": "1988-07-22", "ward": "Emergency", "bed_number": "E-03",
        "allergies": ["Sulfa", "NSAIDs"], "chronic_conditions": ["Asthma"],
        "current_medications": ["Salbutamol inhaler"], "status": "emergency",
        "contact_phone": "+92-321-9876543",
    },
    {
        "full_name": "Muhammad Tariq", "gender": "Male", "blood_type": "B+",
        "date_of_birth": "1942-11-30", "ward": "ICU", "bed_number": "ICU-02",
        "allergies": [], "chronic_conditions": ["COPD", "Heart Failure", "CKD Stage 3"],
        "current_medications": ["Furosemide 40mg", "Carvedilol 25mg", "Spironolactone 25mg"],
        "status": "icu", "contact_phone": "+92-333-5556677",
    },
    {
        "full_name": "Fatima Malik", "gender": "Female", "blood_type": "AB+",
        "date_of_birth": "1995-04-08", "ward": "General Medicine", "bed_number": "GM-07",
        "allergies": ["Codeine"], "chronic_conditions": [],
        "current_medications": [], "status": "active",
        "contact_phone": "+92-345-7778899",
    },
    {
        "full_name": "Zubair Qureshi", "gender": "Male", "blood_type": "O-",
        "date_of_birth": "1978-09-15", "ward": "Neurology", "bed_number": "N-05",
        "allergies": ["Aspirin"], "chronic_conditions": ["Epilepsy", "Hypertension"],
        "current_medications": ["Levetiracetam 500mg", "Amlodipine 5mg"], "status": "active",
        "contact_phone": "+92-312-4443322",
    },
]

DEMO_VITALS = {
    "normal": {"temperature": 36.8, "heart_rate": 74, "systolic_bp": 122, "diastolic_bp": 78, "oxygen_saturation": 98.5, "respiratory_rate": 16, "gcs_score": 15},
    "warning": {"temperature": 38.4, "heart_rate": 102, "systolic_bp": 148, "diastolic_bp": 95, "oxygen_saturation": 93.0, "respiratory_rate": 22, "gcs_score": 14},
    "critical": {"temperature": 39.8, "heart_rate": 128, "systolic_bp": 85, "diastolic_bp": 55, "oxygen_saturation": 87.0, "respiratory_rate": 30, "gcs_score": 10},
}

DEMO_DIAGNOSES = {
    "Ahmad Hassan": [
        {"condition_name": "Hypertensive Heart Disease", "icd_code": "I11.9", "severity": "moderate", "is_primary": True},
        {"condition_name": "Type 2 Diabetes Mellitus", "icd_code": "E11.9", "severity": "mild"},
    ],
    "Sara Khan": [
        {"condition_name": "Acute Severe Asthma", "icd_code": "J45.51", "severity": "severe", "is_primary": True},
    ],
    "Muhammad Tariq": [
        {"condition_name": "Septic Shock", "icd_code": "A41.9", "severity": "critical", "is_primary": True},
        {"condition_name": "Acute on Chronic Heart Failure", "icd_code": "I50.9", "severity": "severe"},
        {"condition_name": "Chronic Obstructive Pulmonary Disease", "icd_code": "J44.1", "severity": "severe"},
        {"condition_name": "Chronic Kidney Disease Stage 3", "icd_code": "N18.3", "severity": "moderate"},
    ],
    "Fatima Malik": [
        {"condition_name": "Community Acquired Pneumonia", "icd_code": "J18.9", "severity": "moderate", "is_primary": True},
    ],
    "Zubair Qureshi": [
        {"condition_name": "Epilepsy - Focal Onset", "icd_code": "G40.2", "severity": "moderate", "is_primary": True},
        {"condition_name": "Essential Hypertension", "icd_code": "I10", "severity": "mild"},
    ],
}

VITAL_PROFILES = {
    "Ahmad Hassan": "warning",
    "Sara Khan": "warning",
    "Muhammad Tariq": "critical",
    "Fatima Malik": "normal",
    "Zubair Qureshi": "normal",
}


async def seed():
    from app.db.session import AsyncSessionLocal, init_db
    from app.services.user_service import UserService
    from app.services.patient_service import PatientService
    from app.models.models import Diagnosis, LabResult

    await init_db()

    async with AsyncSessionLocal() as db:
        # Ensure default users exist
        await UserService.seed_default_users(db)
        await db.commit()

        # Get doctor user
        doctor = await UserService.get_by_email(db, "doctor@cios.hospital")
        if not doctor:
            print("Doctor user not found — run the app first to seed users")
            return

        print("🌱 Seeding demo patients...")

        for pt_data in DEMO_PATIENTS:
            # Create patient
            dob = datetime.strptime(pt_data.pop("date_of_birth"), "%Y-%m-%d")
            pt_data["date_of_birth"] = dob
            pt_data["attending_doctor_id"] = doctor.id
            pt_data["admission_date"] = datetime.utcnow() - timedelta(days=random.randint(1, 10))

            patient = await PatientService.create(db, pt_data, created_by_id=doctor.id)
            print(f"  ✓ Patient: {patient.full_name} ({patient.patient_id})")

            # Record vitals history
            profile_key = VITAL_PROFILES.get(patient.full_name, "normal")
            base_vitals = DEMO_VITALS[profile_key].copy()

            for i in range(8):  # 8 readings
                vitals = {k: v + random.uniform(-2, 2) for k, v in base_vitals.items()}
                vitals = {k: round(v, 1) for k, v in vitals.items()}
                vitals["heart_rate"] = int(vitals["heart_rate"])
                vitals["systolic_bp"] = int(vitals["systolic_bp"])
                vitals["diastolic_bp"] = int(vitals["diastolic_bp"])
                vitals["respiratory_rate"] = int(vitals["respiratory_rate"])
                vitals["gcs_score"] = int(vitals["gcs_score"])
                await PatientService.record_vitals(db, patient.id, vitals, doctor.id)

            # Add diagnoses
            diagnoses = DEMO_DIAGNOSES.get(patient.full_name, [])
            for dx_data in diagnoses:
                dx = Diagnosis(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    treatment_plan=f"Standard protocol for {dx_data['condition_name']}",
                    **dx_data
                )
                db.add(dx)

            # Add lab results
            labs = [
                {"test_name": "Complete Blood Count", "category": "hematology",
                 "results": {"WBC": {"value": round(random.uniform(4, 20), 1), "unit": "x10³/µL", "reference": "4.5-11.0"},
                             "HGB": {"value": round(random.uniform(8, 16), 1), "unit": "g/dL", "reference": "12-17"}},
                 "is_critical": profile_key == "critical"},
                {"test_name": "Basic Metabolic Panel", "category": "chemistry",
                 "results": {"Sodium": {"value": random.randint(130, 148), "unit": "mEq/L", "reference": "136-145"},
                             "Creatinine": {"value": round(random.uniform(0.7, 4.5), 1), "unit": "mg/dL", "reference": "0.6-1.2"}},
                 "is_critical": profile_key == "critical"},
            ]
            for lab_data in labs:
                lab = LabResult(
                    patient_id=patient.id,
                    ordered_by_id=doctor.id,
                    status="resulted",
                    resulted_at=datetime.utcnow(),
                    **lab_data
                )
                db.add(lab)

            await db.flush()

        await db.commit()
        print("\n✅ Demo data seeded successfully!")
        print("   5 patients with vitals, diagnoses, and lab results")
        print("   Run AI assessments from the dashboard to see AI in action")


if __name__ == "__main__":
    asyncio.run(seed())
