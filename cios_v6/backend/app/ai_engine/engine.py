"""
CIOS AI Engine — Clinical Intelligence Core

Implements:
- Risk Prediction with deep feature engineering
- Anomaly Detection (statistical + rule-based)
- Explainable AI (SHAP-style factor attribution)
- Confidence Scoring
- Clinical Digital Twin state modeling
- LLM-based reasoning via Anthropic Claude
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from loguru import logger

from app.core.config import settings


# ─── Output Schemas ──────────────────────────────────────

@dataclass
class RiskPredictionOutput:
    risk_score: float           # 0.0 – 1.0
    risk_level: str             # low | medium | high | critical
    confidence_score: float     # 0.0 – 1.0
    explanation: List[str]      # human-readable reasons
    contributing_factors: Dict[str, float]  # factor: weight
    contradictions: List[str]   # signals that reduce risk
    recommendations: List[str]  # suggested clinical actions
    requires_human_review: bool
    model_version: str = "cios-ai-v1.0"
    prediction_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level,
            "confidence_score": round(self.confidence_score, 4),
            "explanation": self.explanation,
            "contributing_factors": {k: round(v, 4) for k, v in self.contributing_factors.items()},
            "contradictions": self.contradictions,
            "recommendations": self.recommendations,
            "requires_human_review": self.requires_human_review,
            "model_version": self.model_version,
            "prediction_timestamp": self.prediction_timestamp,
        }


@dataclass
class AnomalyResult:
    is_anomaly: bool
    anomaly_score: float
    anomalies_detected: List[Dict[str, Any]]
    severity: str


@dataclass
class DigitalTwinState:
    patient_id: int
    physiological_state: Dict[str, Any]
    disease_trajectory: List[Dict[str, Any]]
    treatment_response: Dict[str, Any]
    what_if_scenarios: List[Dict[str, Any]]
    model_confidence: float
    last_updated: str


# ─── Feature Engineering ─────────────────────────────────

class ClinicalFeatureExtractor:
    """Extracts and normalizes clinical features for AI processing."""

    # Normal ranges for vitals (used for deviation scoring)
    VITAL_RANGES = {
        "temperature": (36.1, 37.2),      # °C normal
        "heart_rate": (60, 100),           # bpm
        "systolic_bp": (90, 140),          # mmHg
        "diastolic_bp": (60, 90),          # mmHg
        "respiratory_rate": (12, 20),      # breaths/min
        "oxygen_saturation": (95, 100),    # %
        "blood_glucose": (70, 140),        # mg/dL
        "gcs_score": (13, 15),             # Glasgow (13+ = normal)
    }

    CRITICAL_THRESHOLDS = {
        "temperature": (35.0, 40.0),
        "heart_rate": (40, 150),
        "systolic_bp": (70, 200),
        "diastolic_bp": (40, 120),
        "respiratory_rate": (8, 35),
        "oxygen_saturation": (85, 100),
        "blood_glucose": (40, 500),
        "gcs_score": (3, 15),
    }

    HIGH_RISK_CONDITIONS = {
        "sepsis": 0.9, "septic shock": 0.95, "cardiac arrest": 1.0,
        "stroke": 0.9, "myocardial infarction": 0.88, "pulmonary embolism": 0.85,
        "respiratory failure": 0.87, "kidney failure": 0.82, "liver failure": 0.85,
        "diabetic ketoacidosis": 0.78, "hypertensive crisis": 0.80,
        "pneumonia": 0.55, "heart failure": 0.72, "copd": 0.60,
        "diabetes": 0.35, "hypertension": 0.30, "asthma": 0.25,
    }

    def extract_vitals_features(self, vitals: List[dict]) -> Dict[str, float]:
        if not vitals:
            return {}

        latest = vitals[-1] if vitals else {}
        features = {}

        # Latest vital deviations from normal
        for vital, (low, high) in self.VITAL_RANGES.items():
            val = latest.get(vital)
            if val is not None:
                normal_mid = (low + high) / 2
                normal_range = high - low
                deviation = abs(val - normal_mid) / (normal_range / 2)
                features[f"{vital}_deviation"] = min(deviation, 3.0)  # cap at 3σ

                # Is it in critical range?
                crit_low, crit_high = self.CRITICAL_THRESHOLDS.get(vital, (0, 999))
                features[f"{vital}_critical"] = 1.0 if (val < crit_low or val > crit_high) else 0.0

        # Trend analysis (last 3 readings)
        if len(vitals) >= 3:
            recent = vitals[-3:]
            for vital in ["heart_rate", "systolic_bp", "oxygen_saturation", "temperature"]:
                vals = [v.get(vital) for v in recent if v.get(vital) is not None]
                if len(vals) >= 2:
                    trend = (vals[-1] - vals[0]) / max(vals[0], 1)
                    features[f"{vital}_trend"] = trend

        return features

    def extract_diagnosis_features(self, diagnoses: List[dict]) -> Dict[str, float]:
        features = {"comorbidity_count": 0, "max_condition_risk": 0.0, "has_critical_dx": 0.0}

        for dx in diagnoses:
            features["comorbidity_count"] += 1
            name = (dx.get("condition_name") or "").lower()
            for condition, risk in self.HIGH_RISK_CONDITIONS.items():
                if condition in name:
                    features["max_condition_risk"] = max(features["max_condition_risk"], risk)
                    if risk > 0.8:
                        features["has_critical_dx"] = 1.0

        return features

    def extract_demographic_features(self, patient: dict) -> Dict[str, float]:
        features = {}
        dob = patient.get("date_of_birth")
        if dob:
            if isinstance(dob, str):
                dob = datetime.fromisoformat(dob.replace("Z", "+00:00"))
            age = (datetime.utcnow() - dob.replace(tzinfo=None)).days / 365
            features["age"] = age
            features["age_risk"] = self._age_risk_score(age)
        features["gender_risk"] = 1.0 if patient.get("gender", "").lower() == "male" else 0.8
        features["allergy_count"] = len(patient.get("allergies", []))
        features["medication_count"] = len(patient.get("current_medications", []))
        return features

    def _age_risk_score(self, age: float) -> float:
        if age < 1: return 0.8
        if age < 18: return 0.3
        if age < 40: return 0.2
        if age < 60: return 0.4
        if age < 75: return 0.6
        return 0.85

    def extract_lab_features(self, labs: List[dict]) -> Dict[str, float]:
        features = {"critical_lab_count": 0, "abnormal_lab_ratio": 0.0}
        if not labs:
            return features

        critical_count = sum(1 for l in labs if l.get("is_critical"))
        features["critical_lab_count"] = critical_count
        features["has_critical_labs"] = 1.0 if critical_count > 0 else 0.0
        return features


# ─── Risk Prediction Model ───────────────────────────────

class RiskPredictionEngine:
    """
    Multi-factor risk prediction with weighted scoring and XAI.
    Uses ensemble approach: rule-based + statistical scoring.
    Designed to be replaced with a trained ML model.
    """

    VERSION = "cios-ai-v1.0"

    FACTOR_WEIGHTS = {
        # Vitals (higher weight due to direct physiological relevance)
        "temperature_deviation": 0.15,
        "temperature_critical": 0.20,
        "heart_rate_deviation": 0.12,
        "heart_rate_critical": 0.18,
        "systolic_bp_deviation": 0.10,
        "systolic_bp_critical": 0.16,
        "oxygen_saturation_deviation": 0.18,
        "oxygen_saturation_critical": 0.25,
        "respiratory_rate_deviation": 0.12,
        "respiratory_rate_critical": 0.20,
        "gcs_score_deviation": 0.15,
        "gcs_score_critical": 0.22,
        # Diagnoses
        "max_condition_risk": 0.35,
        "has_critical_dx": 0.30,
        "comorbidity_count": 0.08,
        # Demographics
        "age_risk": 0.15,
        # Labs
        "critical_lab_count": 0.12,
        "has_critical_labs": 0.18,
        # Trends (worsening is very concerning)
        "heart_rate_trend": 0.10,
        "oxygen_saturation_trend": -0.15,  # negative = dropping is bad
        "systolic_bp_trend": 0.08,
    }

    def __init__(self):
        self.extractor = ClinicalFeatureExtractor()
        self.llm_reasoner = LLMReasoningEngine()

    def predict(self, patient: dict, vitals: List[dict],
                diagnoses: List[dict], labs: List[dict]) -> RiskPredictionOutput:

        # Extract all features
        vital_feats = self.extractor.extract_vitals_features(vitals)
        dx_feats = self.extractor.extract_diagnosis_features(diagnoses)
        demo_feats = self.extractor.extract_demographic_features(patient)
        lab_feats = self.extractor.extract_lab_features(labs)

        all_features = {**vital_feats, **dx_feats, **demo_feats, **lab_feats}

        # Weighted scoring
        weighted_scores = {}
        total_weight = 0
        weighted_sum = 0

        for factor, weight in self.FACTOR_WEIGHTS.items():
            val = all_features.get(factor, 0.0)
            # Normalize trending factors
            if "trend" in factor:
                val = max(0, val * (1.0 if weight >= 0 else -1.0))
                weight = abs(weight)

            normalized_val = min(abs(float(val)), 1.0)
            contribution = normalized_val * weight
            if contribution > 0.01:  # only meaningful contributors
                weighted_scores[factor] = contribution
            weighted_sum += contribution
            total_weight += weight

        raw_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Apply sigmoid-like smoothing for clinical realism
        risk_score = self._sigmoid_scale(raw_score)

        # Confidence: based on data completeness
        confidence = self._calculate_confidence(vitals, diagnoses, labs, all_features)

        # Determine risk level
        risk_level = self._classify_risk(risk_score, all_features)

        # Build XAI explanation
        explanation, factors, contradictions = self._build_explanation(
            all_features, weighted_scores, risk_score, patient, vitals
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(risk_level, all_features, diagnoses)

        requires_review = confidence < settings.AI_CONFIDENCE_THRESHOLD or risk_score > 0.85

        return RiskPredictionOutput(
            risk_score=risk_score,
            risk_level=risk_level,
            confidence_score=confidence,
            explanation=explanation,
            contributing_factors=factors,
            contradictions=contradictions,
            recommendations=recommendations,
            requires_human_review=requires_review,
            model_version=self.VERSION,
        )

    def _sigmoid_scale(self, x: float) -> float:
        """Map raw score to [0,1] with clinical calibration."""
        import math
        return 1 / (1 + math.exp(-8 * (x - 0.4)))

    def _calculate_confidence(self, vitals, diagnoses, labs, features) -> float:
        score = 0.0
        if vitals: score += 0.30
        if len(vitals) >= 3: score += 0.15  # trend data available
        if diagnoses: score += 0.25
        if labs: score += 0.20
        if features.get("age"): score += 0.10
        return min(score, 1.0)

    def _classify_risk(self, score: float, features: dict) -> str:
        if score >= 0.71: return "critical"
        if score >= 0.41: return "moderate"
        return "stable"

    def _build_explanation(self, features, scores, risk_score, patient, vitals
                           ) -> Tuple[List[str], Dict[str, float], List[str]]:
        explanations = []
        contradictions = []
        top_factors = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:8]

        factor_labels = {
            "temperature_critical": "Critical body temperature detected",
            "temperature_deviation": "Significant temperature deviation from normal range",
            "heart_rate_critical": "Heart rate in critical zone",
            "heart_rate_deviation": "Abnormal heart rate",
            "oxygen_saturation_critical": "Critical oxygen saturation — immediate attention required",
            "oxygen_saturation_deviation": "Reduced oxygen saturation",
            "respiratory_rate_critical": "Critical respiratory rate",
            "max_condition_risk": "High-severity primary diagnosis",
            "has_critical_dx": "Life-threatening diagnosis on record",
            "comorbidity_count": f"Multiple comorbidities ({int(features.get('comorbidity_count', 0))})",
            "age_risk": f"Age-associated risk factor (age {int(features.get('age', 0))})",
            "critical_lab_count": f"Critical lab values flagged ({int(features.get('critical_lab_count', 0))})",
            "has_critical_labs": "Critical laboratory results requiring review",
            "gcs_score_critical": "Reduced level of consciousness (GCS critical)",
            "heart_rate_trend": "Worsening heart rate trend over recent readings",
            "oxygen_saturation_trend": "Declining oxygen saturation trend",
        }

        for factor, score in top_factors:
            if score > 0.02:
                label = factor_labels.get(factor, factor.replace("_", " ").title())
                explanations.append(label)

        # Find contradicting (protective) signals
        if features.get("age_risk", 1.0) < 0.25:
            contradictions.append("Young age is a protective factor")
        if features.get("oxygen_saturation_deviation", 1.0) < 0.1:
            contradictions.append("Normal oxygen saturation")
        if features.get("comorbidity_count", 1) == 0:
            contradictions.append("No comorbid conditions on record")
        if not vitals:
            contradictions.append("Insufficient vital signs data — risk may be underestimated")

        # Format contributing factors for output
        contributing = {k: round(v, 4) for k, v in top_factors[:6]}
        return explanations, contributing, contradictions

    def _generate_recommendations(self, risk_level: str,
                                   features: dict, diagnoses: list) -> List[str]:
        recs = []

        if risk_level in ("critical", "moderate"):
            recs.append("Immediate clinical assessment required")
            if risk_level == "critical":
                recs.append("Consider ICU transfer evaluation")

        if features.get("oxygen_saturation_critical"):
            recs.append("Administer supplemental oxygen — assess for respiratory failure")

        if features.get("heart_rate_critical"):
            recs.append("Obtain 12-lead ECG — evaluate for arrhythmia")

        if features.get("temperature_critical"):
            recs.append("Obtain blood cultures — evaluate for sepsis protocol")

        if features.get("gcs_score_critical"):
            recs.append("Neurological assessment — consider CT head")

        if features.get("critical_lab_count", 0) > 0:
            recs.append("Repeat critical lab values and notify attending physician")

        if risk_level == "stable":
            recs.append("Continue standard monitoring protocol")

        if risk_level in ("moderate", "medium"):
            recs.append("Increase monitoring frequency to every 2 hours")
            recs.append("Re-evaluate clinical status within 4 hours")

        return recs[:6]  # Cap at 6 recommendations


# ─── Anomaly Detector ────────────────────────────────────

class AnomalyDetectionEngine:
    """Statistical + rule-based anomaly detection for vitals and labs."""

    def detect(self, vitals: List[dict], labs: List[dict],
               patient: dict) -> AnomalyResult:
        anomalies = []

        # Vital sign anomalies
        if vitals:
            anomalies.extend(self._check_vital_anomalies(vitals))

        # Lab anomalies
        if labs:
            anomalies.extend(self._check_lab_anomalies(labs))

        # Sudden change detection
        if len(vitals) >= 2:
            anomalies.extend(self._detect_sudden_changes(vitals))

        score = min(len(anomalies) * 0.2, 1.0)
        severity = "critical" if score > 0.6 else "warning" if score > 0.3 else "info"

        return AnomalyResult(
            is_anomaly=len(anomalies) > 0,
            anomaly_score=score,
            anomalies_detected=anomalies,
            severity=severity
        )

    def _check_vital_anomalies(self, vitals: List[dict]) -> List[dict]:
        anomalies = []
        latest = vitals[-1]

        checks = [
            ("temperature", 35.0, 40.0, "Body temperature out of safe range"),
            ("heart_rate", 40, 150, "Heart rate critically abnormal"),
            ("systolic_bp", 70, 200, "Systolic BP critically abnormal"),
            ("oxygen_saturation", 85, 100, "Oxygen saturation critically low"),
            ("respiratory_rate", 8, 35, "Respiratory rate critically abnormal"),
            ("gcs_score", 3, 12, "Decreased level of consciousness"),
        ]

        for vital, low, high, msg in checks:
            val = latest.get(vital)
            if val is not None:
                if val < low or val > high:
                    anomalies.append({
                        "type": "critical_vital",
                        "parameter": vital,
                        "value": val,
                        "threshold": {"low": low, "high": high},
                        "message": msg
                    })

        return anomalies

    def _check_lab_anomalies(self, labs: List[dict]) -> List[dict]:
        anomalies = []
        for lab in labs:
            if lab.get("is_critical"):
                anomalies.append({
                    "type": "critical_lab",
                    "test": lab.get("test_name"),
                    "message": f"Critical value: {lab.get('test_name')}"
                })
        return anomalies

    def _detect_sudden_changes(self, vitals: List[dict]) -> List[dict]:
        anomalies = []
        if len(vitals) < 2:
            return anomalies

        prev, curr = vitals[-2], vitals[-1]
        sudden_thresholds = {
            "heart_rate": 30,    # >30 bpm change
            "systolic_bp": 30,   # >30 mmHg
            "oxygen_saturation": 5,  # >5% drop
            "temperature": 1.5,  # >1.5°C
        }

        for vital, threshold in sudden_thresholds.items():
            v1, v2 = prev.get(vital), curr.get(vital)
            if v1 is not None and v2 is not None:
                change = abs(v2 - v1)
                if change > threshold:
                    direction = "increased" if v2 > v1 else "decreased"
                    anomalies.append({
                        "type": "sudden_change",
                        "parameter": vital,
                        "change": round(change, 2),
                        "direction": direction,
                        "message": f"Sudden {direction} in {vital.replace('_', ' ')} ({change:.1f} units)"
                    })

        return anomalies


# ─── Clinical Digital Twin ───────────────────────────────

class ClinicalDigitalTwinEngine:
    """
    Maintains a real-time state model of each patient.
    Simulates disease progression and what-if scenarios.
    """

    def build_state(self, patient: dict, vitals: List[dict],
                    diagnoses: List[dict], labs: List[dict],
                    risk_output: RiskPredictionOutput) -> DigitalTwinState:

        physiological_state = self._build_physiological_state(vitals, labs)
        trajectory = self._project_trajectory(risk_output, physiological_state, diagnoses)
        treatment_response = self._model_treatment_response(diagnoses, patient)
        scenarios = self._generate_what_if_scenarios(risk_output, physiological_state)

        return DigitalTwinState(
            patient_id=patient.get("id", 0),
            physiological_state=physiological_state,
            disease_trajectory=trajectory,
            treatment_response=treatment_response,
            what_if_scenarios=scenarios,
            model_confidence=risk_output.confidence_score,
            last_updated=datetime.utcnow().isoformat()
        )

    def _build_physiological_state(self, vitals: List[dict], labs: List[dict]) -> dict:
        latest_vitals = vitals[-1] if vitals else {}
        # Serialize datetime objects to strings for JSON storage
        safe_vitals = {}
        for k, v in latest_vitals.items():
            if isinstance(v, datetime):
                safe_vitals[k] = v.isoformat()
            else:
                safe_vitals[k] = v
        return {
            "vitals": safe_vitals,
            "vitals_trend": "improving" if self._is_improving(vitals) else "worsening" if self._is_worsening(vitals) else "stable",
            "lab_status": "critical" if any(l.get("is_critical") for l in labs) else "normal",
            "data_freshness_minutes": self._data_age_minutes(latest_vitals),
        }

    def _project_trajectory(self, risk: RiskPredictionOutput, state: dict, diagnoses: list) -> List[dict]:
        now = datetime.utcnow()
        trajectory = []

        # Project based on current risk level
        progression_rate = {
            "critical": 0.04,
            "moderate": 0.02,
            "high": 0.02,
            "medium": 0.00,
            "stable": -0.01,
            "low": -0.01,
        }.get(risk.risk_level, 0.0)

        for hours in [6, 12, 24, 48, 72]:
            projected_score = min(1.0, max(0.0, risk.risk_score + progression_rate * hours))
            level = "critical" if projected_score >= 0.71 else "moderate" if projected_score >= 0.41 else "stable"
            trajectory.append({
                "timestamp": (now + timedelta(hours=hours)).isoformat(),
                "hours_from_now": hours,
                "projected_risk_score": round(projected_score, 3),
                "projected_risk_level": level,
                "confidence": round(max(0.1, risk.confidence_score - hours * 0.01), 3),
            })

        return trajectory

    def _model_treatment_response(self, diagnoses: list, patient: dict) -> dict:
        return {
            "antibiotic_sensitivity": "broad_spectrum_recommended" if any(
                "infection" in str(d.get("condition_name", "")).lower() or
                "sepsis" in str(d.get("condition_name", "")).lower()
                for d in diagnoses
            ) else "not_indicated",
            "expected_improvement_hours": 24 if diagnoses else 0,
            "monitoring_frequency": "hourly" if len(diagnoses) > 2 else "4-hourly",
        }

    def _generate_what_if_scenarios(self, risk: RiskPredictionOutput,
                                     state: dict) -> List[dict]:
        scenarios = [
            {
                "scenario": "early_intervention",
                "description": "If immediate treatment is initiated",
                "projected_risk_change": -0.25,
                "timeframe_hours": 6,
                "interventions": ["IV antibiotics", "O2 therapy", "Fluid resuscitation"],
            },
            {
                "scenario": "no_intervention",
                "description": "If current state continues without intervention",
                "projected_risk_change": +0.15,
                "timeframe_hours": 12,
                "interventions": [],
            },
            {
                "scenario": "icu_transfer",
                "description": "If transferred to ICU for intensive monitoring",
                "projected_risk_change": -0.35,
                "timeframe_hours": 2,
                "interventions": ["ICU monitoring", "Intensivist consultation", "Advanced hemodynamic support"],
            }
        ]
        return scenarios

    def _is_improving(self, vitals: List[dict]) -> bool:
        if len(vitals) < 2:
            return False
        o2_vals = [v.get("oxygen_saturation") for v in vitals[-3:] if v.get("oxygen_saturation")]
        return len(o2_vals) >= 2 and o2_vals[-1] > o2_vals[0]

    def _is_worsening(self, vitals: List[dict]) -> bool:
        if len(vitals) < 2:
            return False
        hr_vals = [v.get("heart_rate") for v in vitals[-3:] if v.get("heart_rate")]
        o2_vals = [v.get("oxygen_saturation") for v in vitals[-3:] if v.get("oxygen_saturation")]
        return (len(hr_vals) >= 2 and hr_vals[-1] > hr_vals[0] + 15) or \
               (len(o2_vals) >= 2 and o2_vals[-1] < o2_vals[0] - 3)

    def _data_age_minutes(self, vitals: dict) -> int:
        recorded = vitals.get("recorded_at")
        if not recorded:
            return 999
        if isinstance(recorded, str):
            recorded = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
        return int((datetime.utcnow() - recorded.replace(tzinfo=None)).total_seconds() / 60)


# ─── LLM Reasoning Engine ────────────────────────────────

class LLMReasoningEngine:
    """Uses Anthropic Claude for deep clinical reasoning and report summarization."""

    def __init__(self):
        self._client = None
        self._available = bool(settings.ANTHROPIC_API_KEY)

    def _get_client(self):
        if self._client is None and self._available:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def generate_clinical_summary(self, patient: dict,
                                         risk_output: RiskPredictionOutput,
                                         vitals: List[dict],
                                         diagnoses: List[dict]) -> str:
        if not self._available:
            return self._fallback_summary(patient, risk_output)

        client = self._get_client()
        prompt = self._build_prompt(patient, risk_output, vitals, diagnoses)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                system="You are an expert clinical decision support AI. Provide concise, accurate medical summaries. Use clinical terminology appropriately. Focus on actionable insights.",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.warning(f"[LLM] API call failed: {e}")
            return self._fallback_summary(patient, risk_output)

    def _build_prompt(self, patient, risk, vitals, diagnoses) -> str:
        latest_vitals = vitals[-1] if vitals else {}
        dx_names = [d.get("condition_name", "") for d in diagnoses[:5]]
        age = "unknown"
        if patient.get("date_of_birth"):
            try:
                dob = datetime.fromisoformat(str(patient["date_of_birth"]).replace("Z", ""))
                age = int((datetime.utcnow() - dob).days / 365)
            except:
                pass

        return f"""Patient Summary Request:
- Patient: {patient.get('full_name', 'Unknown')}, Age: {age}, Gender: {patient.get('gender', 'Unknown')}
- Risk Score: {risk.risk_score:.2f} ({risk.risk_level.upper()})
- Confidence: {risk.confidence_score:.2f}
- Active Diagnoses: {', '.join(dx_names) if dx_names else 'None recorded'}
- Latest Vitals: HR={latest_vitals.get('heart_rate')} bpm, BP={latest_vitals.get('systolic_bp')}/{latest_vitals.get('diastolic_bp')} mmHg, SpO2={latest_vitals.get('oxygen_saturation')}%, Temp={latest_vitals.get('temperature')}°C
- AI Risk Factors: {'; '.join(risk.explanation[:4])}
- Contradictions: {'; '.join(risk.contradictions[:3]) if risk.contradictions else 'None'}

Provide a 3-4 sentence clinical intelligence summary with:
1. Current patient status
2. Primary risk drivers
3. Most important immediate recommendations
Keep it concise, clinical, and actionable."""

    def _fallback_summary(self, patient: dict, risk: RiskPredictionOutput) -> str:
        name = patient.get("full_name", "This patient")
        return (
            f"{name} presents with a {risk.risk_level} risk profile (score: {risk.risk_score:.2f}, "
            f"confidence: {risk.confidence_score:.2f}). "
            f"Key risk factors: {'; '.join(risk.explanation[:3])}. "
            f"{'Immediate clinical review is recommended.' if risk.risk_level in ('moderate', 'critical', 'high') else 'Continue monitoring per protocol.'}"
        )


# ─── Master AI Service ───────────────────────────────────

class CIOSAIEngine:
    """
    Unified AI Engine facade.
    Orchestrates all AI subsystems for a given patient.
    """

    def __init__(self):
        self.risk_engine = RiskPredictionEngine()
        self.anomaly_engine = AnomalyDetectionEngine()
        self.twin_engine = ClinicalDigitalTwinEngine()
        self.llm = LLMReasoningEngine()

    async def full_assessment(self, patient: dict, vitals: List[dict],
                               diagnoses: List[dict], labs: List[dict]) -> dict:
        """
        Complete AI assessment pipeline:
        1. Risk prediction
        2. Anomaly detection
        3. Digital twin update
        4. LLM summary
        """

        # 1. Risk prediction
        risk_output = self.risk_engine.predict(patient, vitals, diagnoses, labs)

        # 2. Anomaly detection
        anomaly_result = self.anomaly_engine.detect(vitals, labs, patient)

        # 3. Digital twin state
        twin_state = self.twin_engine.build_state(
            patient, vitals, diagnoses, labs, risk_output
        )

        # 4. LLM clinical summary
        summary = await self.llm.generate_clinical_summary(
            patient, risk_output, vitals, diagnoses
        )

        return {
            "risk_assessment": risk_output.to_dict(),
            "anomaly_detection": {
                "is_anomaly": anomaly_result.is_anomaly,
                "anomaly_score": anomaly_result.anomaly_score,
                "anomalies": anomaly_result.anomalies_detected,
                "severity": anomaly_result.severity,
            },
            "digital_twin": {
                "physiological_state": twin_state.physiological_state,
                "disease_trajectory": twin_state.disease_trajectory,
                "treatment_response": twin_state.treatment_response,
                "what_if_scenarios": twin_state.what_if_scenarios,
                "model_confidence": twin_state.model_confidence,
                "last_updated": twin_state.last_updated,
            },
            "clinical_summary": summary,
            "alerts_generated": self._generate_alerts(risk_output, anomaly_result),
        }

    def _generate_alerts(self, risk: RiskPredictionOutput,
                          anomaly: AnomalyResult) -> List[dict]:
        alerts = []

        if risk.risk_level == "critical":
            alerts.append({
                "type": "ai_critical_risk",
                "severity": "critical",
                "title": "CRITICAL: AI Risk Assessment",
                "message": f"Patient risk score {risk.risk_score:.0%}. Immediate attention required.",
            })
        elif risk.risk_level in ("moderate", "high"):
            alerts.append({
                "type": "ai_moderate_risk",
                "severity": "warning",
                "title": "Moderate Risk Alert",
                "message": f"AI risk score {risk.risk_score:.0%}. Clinical review recommended.",
            })

        for anom in anomaly.anomalies_detected[:3]:
            if anom.get("type") in ("critical_vital", "sudden_change"):
                alerts.append({
                    "type": "anomaly_detected",
                    "severity": "warning",
                    "title": "Anomaly Detected",
                    "message": anom.get("message", "Clinical anomaly detected"),
                })

        if risk.requires_human_review:
            alerts.append({
                "type": "human_review_required",
                "severity": "info",
                "title": "Human Review Required",
                "message": f"AI confidence {risk.confidence_score:.0%} below threshold. Physician review needed.",
            })

        return alerts


# Global engine instance
_ai_engine: Optional[CIOSAIEngine] = None


def get_ai_engine() -> CIOSAIEngine:
    global _ai_engine
    if _ai_engine is None:
        _ai_engine = CIOSAIEngine()
    return _ai_engine
