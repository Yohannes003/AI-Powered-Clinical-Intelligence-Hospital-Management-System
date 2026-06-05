from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, Enum as SAEnum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    LAB_TECH = "lab_tech"
    VIEWER = "viewer"


class RiskLevel(str, enum.Enum):
    STABLE = "stable"
    MODERATE = "moderate"
    CRITICAL = "critical"
    # Legacy mappings for backward compatibility with existing DB records
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PatientStatus(str, enum.Enum):
    ACTIVE = "active"
    DISCHARGED = "discharged"
    ICU = "icu"
    EMERGENCY = "emergency"
    DECEASED = "deceased"


class EventType(str, enum.Enum):
    PATIENT_CREATED = "patient_created"
    PATIENT_UPDATED = "patient_updated"
    DIAGNOSIS_ADDED = "diagnosis_added"
    LAB_RESULT_UPDATED = "lab_result_updated"
    VITALS_RECORDED = "vitals_recorded"
    AI_PREDICTION_MADE = "ai_prediction_made"
    AI_PIPELINE_COMPLETED = "ai_pipeline_completed"
    TREATMENT_STARTED = "treatment_started"
    ALERT_TRIGGERED = "alert_triggered"
    REPORT_GENERATED = "report_generated"


# ─── Users ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.DOCTOR, nullable=False)
    department = Column(String(100))
    license_number = Column(String(100))
    is_active = Column(Boolean, default=True)
    # RBAC approval fields
    approval_status = Column(String(20), default='approved')  # pending | approved | rejected
    approved_by_id  = Column(Integer, ForeignKey('users.id'), nullable=True)
    approved_at     = Column(DateTime(timezone=True), nullable=True)
    rejection_reason= Column(Text, nullable=True)
    department      = Column(String(100))
    license_number  = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    audit_logs = relationship("AuditLog", back_populates="user")
    ai_predictions = relationship("AIPrediction", back_populates="created_by_user", foreign_keys="AIPrediction.created_by_id")


# ─── Patients ────────────────────────────────────────────
class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(20), unique=True, nullable=False, index=True)  # MRN
    full_name = Column(String(255), nullable=False)
    date_of_birth = Column(DateTime, nullable=False)
    gender = Column(String(20), nullable=False)
    blood_type = Column(String(10))
    contact_phone = Column(String(20))
    contact_email = Column(String(255))
    address = Column(Text)
    emergency_contact = Column(JSON)  # {name, phone, relation}
    allergies = Column(JSON, default=list)
    chronic_conditions = Column(JSON, default=list)
    current_medications = Column(JSON, default=list)
    insurance_info = Column(JSON)
    status = Column(SAEnum(PatientStatus), default=PatientStatus.ACTIVE)
    admission_date = Column(DateTime(timezone=True))
    ward = Column(String(100))
    bed_number = Column(String(20))
    attending_doctor_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    attending_doctor = relationship("User", foreign_keys=[attending_doctor_id])
    visits = relationship("Visit", back_populates="patient", cascade="all, delete-orphan")
    vitals = relationship("VitalSign", back_populates="patient", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="patient", cascade="all, delete-orphan")
    ai_predictions = relationship("AIPrediction", back_populates="patient", cascade="all, delete-orphan")
    digital_twin = relationship("ClinicalDigitalTwin", back_populates="patient", uselist=False, cascade="all, delete-orphan")
    diagnoses = relationship("Diagnosis", back_populates="patient", cascade="all, delete-orphan")


# ─── Visits ──────────────────────────────────────────────
class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    visit_type = Column(String(50))  # emergency, routine, follow_up, icu
    chief_complaint = Column(Text)
    symptoms = Column(JSON, default=list)
    notes = Column(Text)
    visit_date = Column(DateTime(timezone=True), server_default=func.now())
    discharge_date = Column(DateTime(timezone=True))
    status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="visits")
    doctor = relationship("User", foreign_keys=[doctor_id])
    diagnoses = relationship("Diagnosis", back_populates="visit")


# ─── Diagnoses ───────────────────────────────────────────
class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    icd_code = Column(String(20))
    condition_name = Column(String(255), nullable=False)
    severity = Column(String(50))  # mild, moderate, severe, critical
    description = Column(Text)
    treatment_plan = Column(Text)
    medications_prescribed = Column(JSON, default=list)
    is_primary = Column(Boolean, default=False)
    diagnosed_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))

    patient = relationship("Patient", back_populates="diagnoses")
    visit = relationship("Visit", back_populates="diagnoses")
    doctor = relationship("User", foreign_keys=[doctor_id])


# ─── Vital Signs ─────────────────────────────────────────
class VitalSign(Base):
    __tablename__ = "vital_signs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"))
    temperature = Column(Float)          # Celsius
    heart_rate = Column(Integer)         # bpm
    systolic_bp = Column(Integer)        # mmHg
    diastolic_bp = Column(Integer)       # mmHg
    respiratory_rate = Column(Integer)   # breaths/min
    oxygen_saturation = Column(Float)    # %
    blood_glucose = Column(Float)        # mg/dL
    weight = Column(Float)              # kg
    height = Column(Float)              # cm
    gcs_score = Column(Integer)         # Glasgow Coma Scale 3-15
    pain_score = Column(Integer)        # 0-10
    notes = Column(Text)
    is_critical = Column(Boolean, default=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="vitals")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])

    __table_args__ = (Index("idx_vitals_patient_time", "patient_id", "recorded_at"),)


# ─── Lab Results ─────────────────────────────────────────
class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    ordered_by_id = Column(Integer, ForeignKey("users.id"))
    test_name = Column(String(255), nullable=False)
    test_code = Column(String(50))
    category = Column(String(100))  # hematology, chemistry, microbiology
    results = Column(JSON)          # {parameter: {value, unit, reference_range, flag}}
    raw_value = Column(String(500))
    status = Column(String(50), default="pending")  # pending, resulted, reviewed
    is_critical = Column(Boolean, default=False)
    ordered_at = Column(DateTime(timezone=True), server_default=func.now())
    resulted_at = Column(DateTime(timezone=True))
    reviewed_at = Column(DateTime(timezone=True))
    notes = Column(Text)

    patient = relationship("Patient", back_populates="lab_results")
    ordered_by = relationship("User", foreign_keys=[ordered_by_id])


# ─── AI Predictions ──────────────────────────────────────
class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    prediction_type = Column(String(100))   # risk_assessment, anomaly_detection, readmission
    risk_score = Column(Float, nullable=False)
    risk_level = Column(SAEnum(RiskLevel), nullable=False)
    confidence_score = Column(Float, nullable=False)
    explanation = Column(JSON)              # list of human-readable strings
    contributing_factors = Column(JSON)     # {factor: weight}
    contradictions = Column(JSON)          # list of contradicting signals
    recommendations = Column(JSON)         # list of suggested actions
    model_version = Column(String(50))
    requires_review = Column(Boolean, default=False)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"))
    review_notes = Column(Text)
    reviewed_at = Column(DateTime(timezone=True))
    input_snapshot = Column(JSON)          # full input used for prediction
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="ai_predictions")
    created_by_user = relationship("User", foreign_keys=[created_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])


# ─── Clinical Digital Twin ───────────────────────────────
class ClinicalDigitalTwin(Base):
    __tablename__ = "clinical_digital_twins"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), unique=True, nullable=False)
    current_state = Column(JSON)            # full physiological state model
    disease_trajectory = Column(JSON)       # predicted progression timeline
    treatment_response_model = Column(JSON) # expected drug/treatment responses
    what_if_scenarios = Column(JSON)        # list of simulated scenarios
    last_simulation_at = Column(DateTime(timezone=True))
    simulation_count = Column(Integer, default=0)
    model_confidence = Column(Float)
    alert_thresholds = Column(JSON)         # custom thresholds for this patient
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    patient = relationship("Patient", back_populates="digital_twin")


# ─── Audit Logs ──────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(String(100))
    event_type = Column(SAEnum(EventType))
    old_values = Column(JSON)
    new_values = Column(JSON)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    session_id = Column(String(100))
    status = Column(String(50), default="success")  # success, failed, blocked
    error_message = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )


# ─── Event Store ─────────────────────────────────────────
class DomainEvent(Base):
    __tablename__ = "domain_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), unique=True, nullable=False)
    event_type = Column(SAEnum(EventType), nullable=False)
    aggregate_type = Column(String(100))    # Patient, Visit, etc.
    aggregate_id = Column(String(100))
    payload = Column(JSON, nullable=False)
    event_metadata = Column(JSON)           # renamed from 'metadata' (reserved by SQLAlchemy)
    version = Column(Integer, default=1)
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_events_aggregate", "aggregate_type", "aggregate_id"),
        Index("idx_events_unprocessed", "is_processed", "created_at"),
    )


# ─── Alerts ──────────────────────────────────────────────
class ClinicalAlert(Base):
    __tablename__ = "clinical_alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    alert_type = Column(String(100))        # critical_vitals, drug_interaction, ai_risk
    severity = Column(String(50))           # info, warning, critical
    title = Column(String(255))
    message = Column(Text)
    source = Column(String(100))            # ai_engine, rule_engine, lab_system
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by_id = Column(Integer, ForeignKey("users.id"))
    acknowledged_at = Column(DateTime(timezone=True))
    auto_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient")
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_id])


# ─── Reports ─────────────────────────────────────────────
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String(100), unique=True)
    report_type = Column(String(100))       # patient_summary, ai_analysis, department
    title = Column(String(255))
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    generated_by_id = Column(Integer, ForeignKey("users.id"))
    format = Column(String(20))             # pdf, csv, excel, xps
    file_path = Column(String(500))
    ai_summary = Column(Text)
    parameters = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient")
    generated_by = relationship("User", foreign_keys=[generated_by_id])


# ─── Ground Truth Records (GenAI Pipeline) ────────────────
class GroundTruthRecord(Base):
    __tablename__ = "ground_truth_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    ground_truth_summary = Column(Text, nullable=False)
    ai_ml_report_accuracy = Column(Float, default=0.0)
    llm_reasoning_quality = Column(Float, default=0.0)
    overall_confidence = Column(Float, default=0.0)
    discrepancies_found = Column(JSON, default=list)
    corrected_recommendations = Column(JSON, default=list)
    guideline_citations = Column(JSON, default=list)
    ai_ml_snapshot = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient")


# ═══════════════════════════════════════════════════════════
#  MESSAGING & REFERRAL MODELS
# ═══════════════════════════════════════════════════════════

class ConversationStatus(str, enum.Enum):
    ACTIVE   = "active"
    ARCHIVED = "archived"
    CLOSED   = "closed"


class ReferralStatus(str, enum.Enum):
    PENDING   = "pending"
    ACCEPTED  = "accepted"
    DECLINED  = "declined"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReferralPriority(str, enum.Enum):
    ROUTINE = "routine"
    URGENT  = "urgent"
    STAT    = "stat"     # immediate


# ─── Conversation (thread container) ────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id           = Column(Integer, primary_key=True, index=True)
    subject      = Column(String(255), nullable=False)
    patient_id   = Column(Integer, ForeignKey("patients.id"), nullable=True)  # optional context
    created_by_id= Column(Integer, ForeignKey("users.id"), nullable=False)
    status       = Column(SAEnum(ConversationStatus), default=ConversationStatus.ACTIVE)
    is_urgent    = Column(Boolean, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())

    created_by   = relationship("User", foreign_keys=[created_by_id])
    patient      = relationship("Patient", foreign_keys=[patient_id])
    participants = relationship("ConversationParticipant", back_populates="conversation",
                                cascade="all, delete-orphan")
    messages     = relationship("Message", back_populates="conversation",
                                cascade="all, delete-orphan", order_by="Message.created_at")


# ─── Participants ─────────────────────────────────────────
class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_read_at    = Column(DateTime(timezone=True), nullable=True)
    is_muted        = Column(Boolean, default=False)
    joined_at       = Column(DateTime(timezone=True), server_default=func.now())

    conversation    = relationship("Conversation", back_populates="participants")
    user            = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conv_participant"),
    )


# ─── Message ──────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    body            = Column(Text, nullable=False)
    message_type    = Column(String(30), default="text")   # text | system | attachment
    attachment_name = Column(String(255), nullable=True)
    attachment_path = Column(String(500), nullable=True)
    is_edited       = Column(Boolean, default=False)
    edited_at       = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    conversation    = relationship("Conversation", back_populates="messages")
    sender          = relationship("User", foreign_keys=[sender_id])
    receipts        = relationship("MessageReceipt", back_populates="message",
                                   cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_messages_conv_time", "conversation_id", "created_at"),
    )


# ─── Read Receipts ────────────────────────────────────────
class MessageReceipt(Base):
    __tablename__ = "message_receipts"

    id         = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    read_at    = Column(DateTime(timezone=True), server_default=func.now())

    message    = relationship("Message", back_populates="receipts")
    reader     = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_receipt"),
    )


# ─── Referral ─────────────────────────────────────────────
class Referral(Base):
    __tablename__ = "referrals"

    id                   = Column(Integer, primary_key=True, index=True)
    referral_number      = Column(String(30), unique=True, nullable=False)
    patient_id           = Column(Integer, ForeignKey("patients.id"), nullable=False)
    referring_doctor_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    specialist_id        = Column(Integer, ForeignKey("users.id"), nullable=True)  # specific specialist
    specialty_requested  = Column(String(100), nullable=False)   # e.g. Cardiology
    reason               = Column(Text, nullable=False)
    clinical_summary     = Column(Text, nullable=True)
    priority             = Column(SAEnum(ReferralPriority), default=ReferralPriority.ROUTINE)
    status               = Column(SAEnum(ReferralStatus), default=ReferralStatus.PENDING)
    ai_risk_snapshot     = Column(JSON, nullable=True)           # AI risk at time of referral
    diagnosis_ids        = Column(JSON, default=list)            # list of diagnosis IDs included
    attachments          = Column(JSON, default=list)
    notes_from_referring = Column(Text, nullable=True)
    notes_from_specialist= Column(Text, nullable=True)
    accepted_at          = Column(DateTime(timezone=True), nullable=True)
    completed_at         = Column(DateTime(timezone=True), nullable=True)
    follow_up_date       = Column(DateTime(timezone=True), nullable=True)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
    updated_at           = Column(DateTime(timezone=True), onupdate=func.now())

    patient              = relationship("Patient", foreign_keys=[patient_id])
    referring_doctor     = relationship("User", foreign_keys=[referring_doctor_id])
    specialist           = relationship("User", foreign_keys=[specialist_id])
    consultation_notes   = relationship("ConsultationNote", back_populates="referral",
                                        cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_referral_patient",   "patient_id"),
        Index("idx_referral_specialist","specialist_id"),
        Index("idx_referral_status",    "status"),
    )


# ─── Consultation Note ────────────────────────────────────
class ConsultationNote(Base):
    __tablename__ = "consultation_notes"

    id           = Column(Integer, primary_key=True, index=True)
    referral_id  = Column(Integer, ForeignKey("referrals.id"), nullable=False)
    author_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    note_type    = Column(String(50), default="consultation")  # consultation | follow_up | discharge
    title        = Column(String(255))
    body         = Column(Text, nullable=False)
    findings     = Column(Text, nullable=True)
    plan         = Column(Text, nullable=True)
    medications  = Column(JSON, default=list)
    follow_up_in = Column(String(100), nullable=True)   # "2 weeks", "1 month"
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    referral     = relationship("Referral", back_populates="consultation_notes")
    author       = relationship("User", foreign_keys=[author_id])


# ─── Medication Orders ─────────────────────────────────────
class MedicationOrder(Base):
    __tablename__ = "medication_orders"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    medication_name = Column(String(255), nullable=False)
    dose = Column(String(50), nullable=False)
    dose_unit = Column(String(20), default="mg")
    route = Column(String(50), nullable=False)
    frequency = Column(String(50), nullable=False)
    status = Column(String(50), default="active")  # draft, active, on_hold, completed, discontinued, cancelled
    ordered_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    indication = Column(Text)
    notes = Column(Text)
    is_stat = Column(Boolean, default=False)
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    safety_check_passed = Column(Boolean, default=True)
    safety_check_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    patient = relationship("Patient")
    ordered_by = relationship("User", foreign_keys=[ordered_by_id])


# ─── Medication Administration Record (MAR) ───────────────
class MedicationAdministration(Base):
    __tablename__ = "medication_administrations"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("medication_orders.id"), nullable=False)
    administered_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    administered_at = Column(DateTime(timezone=True), nullable=False)
    dose_given = Column(String(50), nullable=False)
    route = Column(String(50))
    site = Column(String(100))
    notes = Column(Text)
    witnessed_by = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("MedicationOrder")
    administered_by = relationship("User", foreign_keys=[administered_by_id])


# ─── Clinical Notes ────────────────────────────────────────
class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note_type = Column(String(50), nullable=False)  # soap, history_and_physical, progress_note, discharge_summary
    content = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    patient = relationship("Patient")
    author = relationship("User", foreign_keys=[author_id])
