"""
Clinical AI Guidelines & Boundaries
Defines rules, constraints, and safety guardrails for AI/ML and GenAI models
operating in the healthcare domain. All models MUST adhere to these boundaries.
"""

CLINICAL_GUIDELINES = {
    "safety_boundaries": {
        "vital_sign_critical_thresholds": {
            "temperature": {"min": 35.0, "max": 40.0, "unit": "°C",
                "action": "Immediate clinical assessment required outside this range"},
            "heart_rate": {"min": 40, "max": 150, "unit": "bpm",
                "action": "Cardiac evaluation recommended"},
            "systolic_bp": {"min": 70, "max": 200, "unit": "mmHg",
                "action": "Hemodynamic assessment required"},
            "oxygen_saturation": {"min": 85, "max": 100, "unit": "%",
                "action": "Respiratory support evaluation needed below threshold"},
            "respiratory_rate": {"min": 8, "max": 35, "unit": "/min",
                "action": "Respiratory assessment recommended"},
        },
        "lab_critical_ranges": {
            "blood_glucose": {"min": 40, "max": 500, "unit": "mg/dL"},
            "gcs_score": {"min": 3, "max": 15, "unit": "score"},
        },
    },
    "ai_transparency": {
        "must_provide_explanation": True,
        "confidence_threshold": 0.75,
        "requires_human_review_when": [
            "confidence_below_threshold",
            "critical_risk_detected",
            "contradictory_signals_present",
            "novel_presentation_no_historical_data",
        ],
        "explanations_must_include": [
            "contributing_factors",
            "contradictions_or_mitigating_factors",
            "recommended_actions",
            "data_quality_assessment",
        ],
    },
    "evidence_based_medicine": {
        "recommendation_levels": ["strongly_recommended", "recommended", "consider", "not_indicated", "contraindicated"],
        "must_cite_guideline_when": [
            "critical_intervention",
            "off_label_treatment",
            "controlled_substance",
        ],
    },
    "human_in_the_loop": {
        "critical_risk_override": "AI cannot override a physician's clinical judgment",
        "always_requires_physician": [
            "treatment_plan_modification",
            "medication_prescription",
            "discharge_decision",
            "surgery_recommendation",
        ],
        "recommendation_escalation": {
            "stable": "no_escalation",
            "low": "no_escalation",
            "moderate": "require_physician_review",
            "medium": "suggest_physician_review",
            "high": "require_physician_review",
            "critical": "immediate_physician_alert",
        },
    },
    "regulatory_compliance": {
        "hipaa": {
            "phi_protection": "All patient data must be de-identified in AI training/summaries",
            "audit_trail": "All AI decisions must be logged with timestamp and user context",
        },
        "fda_ai_ml_saMD": {
            "good_machine_practices": [
                "data_quality_assessment",
                "model_validation",
                "clinical_evaluation",
                "cybersecurity",
            ],
            "transparency": "Users must be informed when interacting with AI-generated content",
            "explainability": "AI recommendations must include reasoning",
        },
    },
    "data_quality": {
        "minimum_vitals_for_risk_assessment": 1,
        "minimum_diagnoses_for_trajectory": 1,
        "data_freshness_max_minutes": 120,
        "incomplete_data_protocol": "Flag uncertainty when data is insufficient",
    },
    "gen_ai_boundaries": {
        "must_not": [
            "invent_clinical_data",
            "override_physician_judgment",
            "provide_definitive_diagnosis_without_human_validation",
            "recommend_unapproved_treatments",
            "disclose_patient_identity",
        ],
        "must_always": [
            "acknowledge_uncertainty",
            "cite_evidence_level",
            "flag_confidence",
            "identify_as_ai_generated",
        ],
    },
}


def check_vital_safety(vital_name: str, value: float) -> dict:
    bounds = CLINICAL_GUIDELINES["safety_boundaries"]["vital_sign_critical_thresholds"].get(vital_name)
    if not bounds:
        return {"safe": True, "violation": None}
    if value < bounds["min"] or value > bounds["max"]:
        return {"safe": False, "violation": f"{vital_name} ({value} {bounds['unit']}) outside safe range", "action": bounds["action"]}
    return {"safe": True, "violation": None}


def check_guideline_compliance(risk_level: str, confidence: float) -> dict:
    compliance = {"human_review_required": True, "reasons": [], "escalation": None}

    if confidence < CLINICAL_GUIDELINES["ai_transparency"]["confidence_threshold"]:
        compliance["reasons"].append("AI confidence below threshold")

    escalation_map = CLINICAL_GUIDELINES["human_in_the_loop"]["recommendation_escalation"]
    compliance["escalation"] = escalation_map.get(risk_level, "no_escalation")

    if risk_level in ("critical", "moderate", "high"):
        tag = risk_level.upper()
        compliance["reasons"].append(f"{tag} risk detected — physician review required")

    if not compliance["reasons"]:
        compliance["human_review_required"] = False

    return compliance
