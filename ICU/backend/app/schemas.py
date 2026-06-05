"""
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ============== Patient Schemas ==============

class PatientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)
    gender: str = Field(..., pattern="^(male|female|other)$")
    bed_number: str = Field(..., min_length=1, max_length=20)
    diagnosis: Optional[str] = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    gender: Optional[str] = None
    bed_number: Optional[str] = None
    diagnosis: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(stable|critical|recovered)$")
    is_active: Optional[bool] = None


class PatientResponse(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    risk_score: float
    is_active: bool
    admission_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    vital_count: Optional[int] = 0
    alert_count: Optional[int] = 0


class PatientListResponse(BaseModel):
    patients: List[PatientResponse]
    total: int


# ============== Vital Sign Schemas ==============

class VitalSignBase(BaseModel):
    heart_rate: Optional[float] = Field(None, ge=0, le=300)
    blood_pressure_systolic: Optional[float] = Field(None, ge=0, le=300)
    blood_pressure_diastolic: Optional[float] = Field(None, ge=0, le=200)
    mean_arterial_pressure: Optional[float] = None
    respiratory_rate: Optional[float] = Field(None, ge=0, le=100)
    spo2: Optional[float] = Field(None, ge=0, le=100)
    etco2: Optional[float] = None
    temperature: Optional[float] = None
    gcs_score: Optional[int] = Field(None, ge=3, le=15)
    pain_score: Optional[int] = Field(None, ge=0, le=10)
    urine_output: Optional[float] = None
    central_venous_pressure: Optional[float] = None


class VitalSignCreate(VitalSignBase):
    patient_id: int
    risk_score: Optional[float] = 0.0
    risk_level: Optional[str] = "low"


class VitalSignResponse(VitalSignBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    timestamp: datetime
    risk_score: float
    risk_level: str


class VitalSignHistory(BaseModel):
    vitals: List[VitalSignResponse]
    patient_id: int
    total: int


class RealTimeVital(BaseModel):
    """Real-time vital sign update via WebSocket."""
    patient_id: int
    patient_name: str
    bed_number: str
    timestamp: str
    heart_rate: Optional[float] = None
    blood_pressure_systolic: Optional[float] = None
    blood_pressure_diastolic: Optional[float] = None
    respiratory_rate: Optional[float] = None
    spo2: Optional[float] = None
    temperature: Optional[float] = None
    gcs_score: Optional[int] = None
    risk_score: float = 0.0
    risk_level: str = "low"
    alert_triggered: Optional[bool] = False
    alert_message: Optional[str] = None


# ============== Alert Schemas ==============

class AlertBase(BaseModel):
    alert_type: str
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    message: str


class AlertCreate(AlertBase):
    patient_id: int
    vital_sign_snapshot: Optional[Dict[str, Any]] = None


class AlertResponse(AlertBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    timestamp: datetime
    acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool
    resolved_at: Optional[datetime] = None
    vital_sign_snapshot: Optional[Dict[str, Any]] = None


class AlertAcknowledge(BaseModel):
    acknowledged_by: str = Field(..., min_length=1)


class AlertStats(BaseModel):
    total_alerts: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    unacknowledged_count: int


# ============== Report Schemas ==============

class ReportCreate(BaseModel):
    patient_id: int
    report_type: str = Field(default="summary", pattern="^(summary|detailed|trend)$")


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    generated_at: datetime
    report_type: str
    content: str
    vital_summary: Optional[Dict[str, Any]] = None
    risk_trend: Optional[Dict[str, Any]] = None
    recommendations: Optional[str] = None
    generated_by: str


# ============== Dashboard Schemas ==============

class DashboardStats(BaseModel):
    total_patients: int
    active_patients: int
    critical_patients: int
    total_alerts_today: int
    unacknowledged_alerts: int
    avg_risk_score: float
    recent_alerts: List[AlertResponse]


class RiskDistribution(BaseModel):
    stable: int = 0
    moderate: int = 0
    critical: int = 0


# ============== WebSocket Message Schemas ==============

class WSMessage(BaseModel):
    type: str  # vital_update, alert, patient_update, connected
    data: Dict[str, Any]
    timestamp: str
