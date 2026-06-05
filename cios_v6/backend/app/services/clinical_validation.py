"""
Clinical Data Validation — physiological plausibility checks for all clinical data.
Rejects impossible vitals at input rather than just flagging them.
"""
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ValidationResult:
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    normalized: Dict[str, Any] = field(default_factory=dict)


PHYSIOLOGICAL_RANGES: Dict[str, Dict] = {
    "temperature": {
        "min": 32.0, "max": 42.0, "unit": "°C",
        "error": "Temperature {val}°C is physiologically impossible",
        "warning_min": 35.0, "warning_max": 40.0,
        "warning": "Temperature {val}°C is outside safe clinical range [{warn_min}-{warn_max}]",
        "type": float,
    },
    "heart_rate": {
        "min": 10, "max": 300, "unit": "bpm",
        "error": "Heart rate {val} bpm is physiologically impossible",
        "warning_min": 30, "warning_max": 220,
        "warning": "Heart rate {val} bpm outside expected range [{warn_min}-{warn_max}]",
        "type": int,
    },
    "systolic_bp": {
        "min": 30, "max": 300, "unit": "mmHg",
        "error": "Systolic BP {val} mmHg is physiologically impossible",
        "warning_min": 60, "warning_max": 250,
        "warning": "Systolic BP {val} mmHg outside expected range",
        "type": int,
    },
    "diastolic_bp": {
        "min": 10, "max": 200, "unit": "mmHg",
        "error": "Diastolic BP {val} mmHg is physiologically impossible",
        "warning_min": 30, "warning_max": 140,
        "warning": "Diastolic BP {val} mmHg outside expected range",
        "type": int,
    },
    "respiratory_rate": {
        "min": 1, "max": 80, "unit": "/min",
        "error": "Respiratory rate {val}/min is physiologically impossible",
        "warning_min": 6, "warning_max": 50,
        "warning": "Respiratory rate {val}/min outside expected range",
        "type": int,
    },
    "oxygen_saturation": {
        "min": 10, "max": 100, "unit": "%",
        "error": "O2 saturation {val}% is physiologically impossible",
        "warning_min": 50, "warning_max": 100,
        "warning": "O2 saturation {val}% critically low",
        "type": float,
    },
    "blood_glucose": {
        "min": 5, "max": 1000, "unit": "mg/dL",
        "error": "Blood glucose {val} mg/dL is physiologically impossible",
        "warning_min": 40, "warning_max": 600,
        "warning": "Blood glucose {val} mg/dL outside expected range",
        "type": float,
    },
    "gcs_score": {
        "min": 3, "max": 15, "unit": "score",
        "error": "GCS score {val} must be between 3 and 15",
        "warning_min": 3, "warning_max": 15,
        "type": int,
    },
    "pain_score": {
        "min": 0, "max": 10, "unit": "score",
        "error": "Pain score {val} must be between 0 and 10",
        "warning_min": 0, "warning_max": 10,
        "type": int,
    },
    "weight": {
        "min": 0.5, "max": 500, "unit": "kg",
        "error": "Weight {val} kg is physiologically impossible",
        "warning_min": 2, "warning_max": 350,
        "type": float,
    },
    "height": {
        "min": 10, "max": 300, "unit": "cm",
        "error": "Height {val} cm is physiologically impossible",
        "warning_min": 30, "warning_max": 250,
        "type": float,
    },
}

RELATIONAL_CHECKS = [
    {
        "name": "bp_systolic_gt_diastolic",
        "fields": ["systolic_bp", "diastolic_bp"],
        "check": lambda s, d: s <= d if s is not None and d is not None else False,
        "error": "Systolic BP ({s}) must be greater than diastolic BP ({d})",
    },
    {
        "name": "bp_pulse_pressure",
        "fields": ["systolic_bp", "diastolic_bp"],
        "check": lambda s, d: (s - d) < 10 if s is not None and d is not None else False,
        "warning": "Narrow pulse pressure ({pp} mmHg) — may indicate reduced cardiac output",
    },
    {
        "name": "temp_hr_correlation",
        "fields": ["temperature", "heart_rate"],
        "check": lambda t, hr: hr > 120 and t < 36.0 if hr is not None and t is not None else False,
        "warning": "Tachycardia with hypothermia — consider sepsis despite low temp",
    },
    {
        "name": "hr_bp_correlation",
        "fields": ["heart_rate", "systolic_bp"],
        "check": lambda hr, sbp: hr > 120 and sbp < 90 if hr is not None and sbp is not None else False,
        "warning": "Tachycardia + hypotension — signs of hemodynamic instability",
    },
]


def validate_vitals(vitals: Dict[str, Any]) -> ValidationResult:
    errors = []
    warnings = []
    normalized = {}

    for field, value in vitals.items():
        if value is None:
            continue
        config = PHYSIOLOGICAL_RANGES.get(field)
        if not config:
            normalized[field] = value
            continue

        try:
            typed_val = config["type"](value)
        except (ValueError, TypeError):
            errors.append(f"{field}: cannot interpret value '{value}'")
            continue

        if typed_val < config["min"] or typed_val > config["max"]:
            errors.append(config["error"].format(val=typed_val))
            continue

        if "warning_min" in config and "warning_max" in config:
            if typed_val < config["warning_min"] or typed_val > config["warning_max"]:
                warning_msg = config.get("warning", "").format(
                    val=typed_val, warn_min=config["warning_min"], warn_max=config["warning_max"]
                )
                if warning_msg:
                    warnings.append(warning_msg)

        normalized[field] = typed_val

    systolic = normalized.get("systolic_bp", vitals.get("systolic_bp"))
    diastolic = normalized.get("diastolic_bp", vitals.get("diastolic_bp"))

    for check in RELATIONAL_CHECKS:
        vals = []
        for f in check["fields"]:
            v = normalized.get(f, vitals.get(f))
            vals.append(v)

        try:
            if check["check"](*vals):
                msg = check.get("error") or check.get("warning", "")
                formatted = msg.format(**{check["fields"][i]: vals[i] for i in range(len(vals))})
                try:
                    formatted = formatted.format(
                        s=vals[0], d=vals[1], pp=(vals[0] - vals[1]) if vals[0] and vals[1] else 0
                    )
                except Exception:
                    pass
                if "error" in check:
                    errors.append(formatted)
                else:
                    warnings.append(formatted)
        except Exception:
            pass

    return ValidationResult(
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        normalized=normalized,
    )


def validate_age(age_years: float) -> ValidationResult:
    errors = []
    warnings = []
    if age_years < 0:
        errors.append("Age cannot be negative")
    elif age_years > 150:
        warnings.append(f"Age {age_years} exceeds maximum documented human lifespan")
    elif age_years > 130:
        errors.append(f"Age {age_years} is not physiologically plausible")
    return ValidationResult(passed=len(errors) == 0, errors=errors, warnings=warnings)
