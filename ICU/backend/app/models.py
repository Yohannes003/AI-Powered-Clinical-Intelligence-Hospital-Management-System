"""
SQLAlchemy models for the ICU Monitoring System.
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Patient(Base):
    """ICU Patient model."""
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)
    bed_number = Column(String(20), unique=True, nullable=False)
    admission_date = Column(DateTime(timezone=True), server_default=func.now())
    diagnosis = Column(Text, nullable=True)
    status = Column(String(20), default="stable")  # stable, critical, recovered
    risk_score = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    vitals = relationship("VitalSign", back_populates="patient", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="patient", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="patient", cascade="all, delete-orphan")


class VitalSign(Base):
    """Real-time vital signs from patient monitors."""
    __tablename__ = "vital_signs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Cardiovascular
    heart_rate = Column(Float, nullable=True)  # BPM
    blood_pressure_systolic = Column(Float, nullable=True)  # mmHg
    blood_pressure_diastolic = Column(Float, nullable=True)  # mmHg
    mean_arterial_pressure = Column(Float, nullable=True)  # mmHg

    # Respiratory
    respiratory_rate = Column(Float, nullable=True)  # breaths/min
    spo2 = Column(Float, nullable=True)  # %
    etco2 = Column(Float, nullable=True)  # mmHg

    # Temperature
    temperature = Column(Float, nullable=True)  # Celsius

    # Neurological
    gcs_score = Column(Integer, nullable=True)  # Glasgow Coma Scale (3-15)
    pain_score = Column(Integer, nullable=True)  # 0-10

    # Other
    urine_output = Column(Float, nullable=True)  # mL/hour
    central_venous_pressure = Column(Float, nullable=True)  # mmHg

    # Computed risk
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String(20), default="low")  # low, medium, high, critical

    # Relationship
    patient = relationship("Patient", back_populates="vitals")


class Alert(Base):
    """Clinical alerts and notifications."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    alert_type = Column(String(50), nullable=False)  # cardiac, respiratory, neurological, etc.
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    message = Column(Text, nullable=False)
    vital_sign_snapshot = Column(JSON, nullable=True)  # snapshot of vitals when alert fired
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    patient = relationship("Patient", back_populates="alerts")


class Report(Base):
    """AI-generated clinical reports."""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    report_type = Column(String(50), default="summary")  # summary, detailed, trend
    content = Column(Text, nullable=False)
    vital_summary = Column(JSON, nullable=True)
    risk_trend = Column(JSON, nullable=True)
    recommendations = Column(Text, nullable=True)
    generated_by = Column(String(50), default="ai")  # ai, physician

    # Relationship
    patient = relationship("Patient", back_populates="reports")
