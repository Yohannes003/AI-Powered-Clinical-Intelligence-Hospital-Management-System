"""
Clinical Risk Prediction Engine using XGBoost.
Predicts patient deterioration risk based on vital signs.
Falls back to rule-based scoring if model is not available.
"""

import os
import pickle
import logging
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Paths
MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml", "heart_model.pkl")

# Feature order expected by the model
FEATURE_ORDER = [
    "age",
    "heart_rate",
    "blood_pressure_systolic",
    "blood_pressure_diastolic",
    "respiratory_rate",
    "spo2",
    "temperature",
    "gcs_score",
]


class RiskEngine:
    """
    Clinical Risk Prediction Engine.
    Uses XGBoost model when available, falls back to rule-based scoring.
    """

    RISK_STABLE = 0.41
    RISK_MODERATE = 0.71

    def __init__(self):
        self.model = None
        self.scaler = None
        self.model_available = False
        self._load_model()

    def _load_model(self):
        """Load the pre-trained XGBoost model."""
        try:
            if os.path.exists(MODEL_PATH):
                with open(MODEL_PATH, "rb") as f:
                    model_data = pickle.load(f)
                    if isinstance(model_data, dict):
                        self.model = model_data.get("model")
                        self.scaler = model_data.get("scaler")
                    else:
                        self.model = model_data
                self.model_available = True
                logger.info(f"XGBoost model loaded from {MODEL_PATH}")
            else:
                logger.warning(f"Model file not found at {MODEL_PATH}. Using rule-based scoring.")
        except Exception as e:
            logger.error(f"Error loading model: {e}. Using rule-based scoring.")
            self.model_available = False

    def _rule_based_score(self, vitals: Dict, age: int = 65) -> Tuple[float, str]:
        """
        Calculate risk score using clinical rules (NEWS2-inspired).
        Returns: (risk_score, risk_level)
        """
        score = 0.0
        max_score = 20.0  # Normalized to 0-1

        # Heart rate scoring (0-3 points)
        hr = vitals.get("heart_rate")
        if hr is not None:
            if hr < 40 or hr > 130:
                score += 3
            elif hr < 50 or hr > 110:
                score += 2
            elif hr < 60 or hr > 100:
                score += 1

        # Systolic BP scoring (0-3 points)
        sys_bp = vitals.get("blood_pressure_systolic")
        if sys_bp is not None:
            if sys_bp < 90 or sys_bp > 220:
                score += 3
            elif sys_bp < 100:
                score += 2
            elif sys_bp < 110:
                score += 1

        # Respiratory rate scoring (0-3 points)
        rr = vitals.get("respiratory_rate")
        if rr is not None:
            if rr < 8 or rr > 25:
                score += 3
            elif rr < 11 or rr > 20:
                score += 2
            elif rr < 12 or rr > 16:
                score += 1

        # SpO2 scoring (0-3 points)
        spo2 = vitals.get("spo2")
        if spo2 is not None:
            if spo2 < 85:
                score += 3
            elif spo2 < 88:
                score += 2
            elif spo2 < 92:
                score += 1

        # Temperature scoring (0-3 points)
        temp = vitals.get("temperature")
        if temp is not None:
            if temp < 35.0 or temp > 39.0:
                score += 3
            elif temp < 36.0 or temp > 38.0:
                score += 2
            elif temp < 36.5 or temp > 37.5:
                score += 1

        # GCS scoring (0-3 points) - lower is worse
        gcs = vitals.get("gcs_score")
        if gcs is not None:
            if gcs < 9:
                score += 3
            elif gcs < 13:
                score += 2
            elif gcs < 15:
                score += 1

        # Age factor
        if age > 75:
            score += 2
        elif age > 65:
            score += 1

        # Normalize to 0-1 range
        risk_score = min(score / max_score, 1.0)

        # Add some randomness for realistic fluctuation (small)
        noise = np.random.normal(0, 0.03)
        risk_score = max(0, min(1, risk_score + noise))

        return risk_score, self._get_risk_level(risk_score)

    def _ml_predict(self, features: np.ndarray) -> Tuple[float, str]:
        """Make prediction using the XGBoost model."""
        try:
            # Scale features if scaler available
            if self.scaler:
                features = self.scaler.transform(features.reshape(1, -1))
            else:
                features = features.reshape(1, -1)

            # Predict probability
            if hasattr(self.model, "predict_proba"):
                risk_score = float(self.model.predict_proba(features)[0][1])
            else:
                risk_score = float(self.model.predict(features)[0])

            # Clip to valid range
            risk_score = max(0, min(1, risk_score))
            return risk_score, self._get_risk_level(risk_score)
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return 0.8, "critical"

    def _get_risk_level(self, score: float) -> str:
        if score >= self.RISK_MODERATE:
            return "critical"
        elif score >= self.RISK_STABLE:
            return "moderate"
        return "stable"

    def predict(self, vitals: Dict, age: int = 65) -> Dict:
        """
        Predict risk based on vital signs.
        Returns dict with risk_score, risk_level, and contributing_factors.
        """
        if self.model_available:
            # Prepare feature vector
            features = np.array([
                age,
                vitals.get("heart_rate", 75) or 75,
                vitals.get("blood_pressure_systolic", 120) or 120,
                vitals.get("blood_pressure_diastolic", 80) or 80,
                vitals.get("respiratory_rate", 16) or 16,
                vitals.get("spo2", 98) or 98,
                vitals.get("temperature", 37.0) or 37.0,
                vitals.get("gcs_score", 15) or 15,
            ])

            # Handle missing values with medians
            features = np.nan_to_num(features, nan=0)

            risk_score, risk_level = self._ml_predict(features)
        else:
            risk_score, risk_level = self._rule_based_score(vitals, age)

        # Identify contributing factors
        contributing_factors = self._identify_factors(vitals)

        return {
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
            "contributing_factors": contributing_factors,
            "model_used": "xgboost" if self.model_available else "rule_based",
            "timestamp": datetime.now().isoformat()
        }

    def _identify_factors(self, vitals: Dict) -> list:
        """Identify clinical factors contributing to risk."""
        factors = []

        hr = vitals.get("heart_rate")
        if hr is not None and (hr < 50 or hr > 120):
            factors.append(f"Abnormal heart rate: {hr} bpm")

        sys_bp = vitals.get("blood_pressure_systolic")
        if sys_bp is not None and (sys_bp < 90 or sys_bp > 180):
            factors.append(f"Abnormal blood pressure: {sys_bp} mmHg")

        rr = vitals.get("respiratory_rate")
        if rr is not None and (rr < 10 or rr > 30):
            factors.append(f"Abnormal respiratory rate: {rr}/min")

        spo2 = vitals.get("spo2")
        if spo2 is not None and spo2 < 92:
            factors.append(f"Low oxygen saturation: {spo2}%")

        temp = vitals.get("temperature")
        if temp is not None and (temp < 36.0 or temp > 38.5):
            factors.append(f"Abnormal temperature: {temp}°C")

        gcs = vitals.get("gcs_score")
        if gcs is not None and gcs < 13:
            factors.append(f"Reduced consciousness: GCS {gcs}")

        return factors

    def check_alert_thresholds(self, vitals: Dict, patient_name: str = "Patient") -> Optional[Dict]:
        """
        Check if vitals trigger any alert thresholds.
        Returns alert data if triggered, None otherwise.
        """
        alerts = []
        severity = "medium"

        hr = vitals.get("heart_rate")
        if hr is not None:
            if hr < 40 or hr > 150:
                alerts.append(f"CRITICAL: Heart rate {hr} bpm")
                severity = "critical"
            elif hr < 50 or hr > 130:
                alerts.append(f"High risk: Heart rate {hr} bpm")
                severity = max_severity(severity, "high")

        sys_bp = vitals.get("blood_pressure_systolic")
        if sys_bp is not None:
            if sys_bp < 80 or sys_bp > 200:
                alerts.append(f"CRITICAL: Systolic BP {sys_bp} mmHg")
                severity = "critical"
            elif sys_bp < 90:
                alerts.append(f"High risk: Hypotension {sys_bp} mmHg")
                severity = max_severity(severity, "high")

        spo2 = vitals.get("spo2")
        if spo2 is not None:
            if spo2 < 85:
                alerts.append(f"CRITICAL: Severe hypoxemia SpO2 {spo2}%")
                severity = "critical"
            elif spo2 < 90:
                alerts.append(f"High risk: Hypoxemia SpO2 {spo2}%")
                severity = max_severity(severity, "high")

        rr = vitals.get("respiratory_rate")
        if rr is not None:
            if rr < 8 or rr > 35:
                alerts.append(f"CRITICAL: Respiratory rate {rr}/min")
                severity = "critical"
            elif rr > 25:
                alerts.append(f"High risk: Tachypnea {rr}/min")
                severity = max_severity(severity, "high")

        temp = vitals.get("temperature")
        if temp is not None:
            if temp < 34.0 or temp > 40.0:
                alerts.append(f"CRITICAL: Temperature {temp}°C")
                severity = "critical"

        gcs = vitals.get("gcs_score")
        if gcs is not None and gcs < 9:
            alerts.append(f"CRITICAL: Severe GCS impairment {gcs}")
            severity = "critical"

        if not alerts:
            return None

        alert_type = "cardiac" if any("Heart" in a or "BP" in a for a in alerts) else \
                     "respiratory" if any("Respiratory" in a or "SpO2" in a for a in alerts) else \
                     "neurological" if any("GCS" in a for a in alerts) else "general"

        return {
            "alert_type": alert_type,
            "severity": severity,
            "message": "; ".join(alerts),
            "vital_sign_snapshot": vitals,
            "timestamp": datetime.now().isoformat()
        }


# Severity comparison helper
def max_severity(a: str, b: str) -> str:
    """Return the more severe of two severity levels."""
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return a if order.get(a, 0) >= order.get(b, 0) else b


# Singleton instance
risk_engine = RiskEngine()
