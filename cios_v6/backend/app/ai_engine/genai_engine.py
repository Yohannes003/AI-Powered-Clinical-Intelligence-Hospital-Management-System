"""
GenAI Ground Truth Engine
Takes AI/ML report + LLM analysis as input and produces ground truth (reality)
assessment based on clinical guidelines and evidence-based medicine boundaries.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
from loguru import logger
from dataclasses import dataclass, field

from app.core.config import settings
from app.ai_engine.guidelines import CLINICAL_GUIDELINES, check_guideline_compliance


@dataclass
class GroundTruthOutput:
    ground_truth_summary: str
    validation_against_guidelines: Dict[str, Any]
    ai_ml_report_accuracy: float
    llm_reasoning_quality: float
    overall_confidence: float
    discrepancies_found: List[str]
    corrected_recommendations: List[str]
    guideline_citations: List[str]
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "ground_truth_summary": self.ground_truth_summary,
            "validation_against_guidelines": self.validation_against_guidelines,
            "ai_ml_report_accuracy": round(self.ai_ml_report_accuracy, 4),
            "llm_reasoning_quality": round(self.llm_reasoning_quality, 4),
            "overall_confidence": round(self.overall_confidence, 4),
            "discrepancies_found": self.discrepancies_found,
            "corrected_recommendations": self.corrected_recommendations,
            "guideline_citations": self.guideline_citations,
            "generated_at": self.generated_at,
        }


class GenAIGroundTruthEngine:
    """Produces ground truth by validating AI/ML and LLM outputs against clinical guidelines."""

    def __init__(self):
        self._client = None
        self._available = bool(settings.ANTHROPIC_API_KEY)

    def _get_client(self):
        if self._client is None and self._available:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def generate_ground_truth(
        self,
        patient: dict,
        ai_ml_report: dict,
        llm_analysis: str,
        vitals: List[dict],
        diagnoses: List[dict],
        labs: List[dict],
    ) -> GroundTruthOutput:
        if self._available:
            return await self._llm_ground_truth(patient, ai_ml_report, llm_analysis, vitals, diagnoses, labs)
        return self._rule_based_ground_truth(patient, ai_ml_report, llm_analysis, vitals, diagnoses, labs)

    async def _llm_ground_truth(
        self, patient, ai_ml_report, llm_analysis, vitals, diagnoses, labs
    ) -> GroundTruthOutput:
        client = self._get_client()
        prompt = self._build_prompt(patient, ai_ml_report, llm_analysis, vitals, diagnoses, labs)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                system=(
                    "You are a senior physician supervising an AI clinical decision support system. "
                    "Your role is to validate the AI's findings against evidence-based medical guidelines "
                    "and provide the ground truth (clinical reality). Be conservative, cautious, and precise. "
                    "Always flag uncertainty. Cite guideline sources where applicable.\n\n"
                    "RISK CLASSIFICATION:\n"
                    "- 🟢 0-40%: Stable — standard monitoring\n"
                    "- 🟡 41-70%: Moderate Risk (Requires Monitoring) — physician review recommended\n"
                    "- 🔴 71-100%: Critical (Immediate Attention Required) — immediate physician alert\n\n"
                    "REGULATORY FRAMEWORK (Healthcare AI Guidelines):\n"
                    "- FDA (US): SaMD classification, 510(k)/De Novo/PMA pathways; GMLP principles "
                    "(data quality, model validation, clinical evaluation, cybersecurity)\n"
                    "- EU MDR (2017/745): CE marking via Notified Body; AI Act classifies clinical AI as high-risk, "
                    "requiring risk management, data quality, transparency, human oversight\n"
                    "- UK MHRA: UKCA marking; change programme roadmap emphasizing safety, transparency, adaptivity\n"
                    "- HIPAA: PHI protection, de-identification (Safe Harbor/Expert), breach notification, "
                    "administrative/technical safeguards\n"
                    "- GDPR: special category data protection, lawful basis (consent/public interest), "
                    "DPIAs for high-risk AI, 72h breach notification\n\n"
                    "STANDARDS:\n"
                    "- ISO 13485 (QMS), ISO 14971 (risk management — extend for AI hazards: dataset shift, "
                    "model drift, bias), IEC 62304 (software lifecycle), IEC 62366 (usability engineering)\n"
                    "- IEC 81001-5-1 (cybersecurity), ISO/IEC 27001 (information security)\n"
                    "- IMDRF Good ML Practice: 10 principles covering design, data, training, testing, transparency\n\n"
                    "VALIDATION REQUIREMENTS:\n"
                    "- Analytical validation: ROC AUC, sensitivity, specificity on held-out test sets\n"
                    "- Clinical validation: retrospective/prospective studies, subgroup analysis for bias\n"
                    "- Model calibration, uncertainty quantification (Bayesian/ensemble)\n"
                    "- Explainability: SHAP/LIME, saliency maps for clinician trust\n\n"
                    "ETHICS & SAFETY:\n"
                    "- Human-in-the-loop: AI cannot override physician judgment\n"
                    "- Transparency: disclose AI role to clinicians and patients; provide intelligible explanations\n"
                    "- Fairness: fairness audits, remediate inequities, prioritize disadvantaged groups\n"
                    "- Post-market surveillance: monitor drift (PSI/KL divergence), periodic safety reviews\n"
                    "- Incident response: adverse event reporting, root cause analysis, update risk file\n"
                    "- Documentation: traceability matrix, versioned code/data, change logs, audit trail (ALCOA)"
                ),
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text
            return self._parse_llm_response(text, ai_ml_report)
        except Exception as e:
            logger.warning(f"[GenAI] API call failed: {e}")
            return self._rule_based_ground_truth(patient, ai_ml_report, llm_analysis, vitals, diagnoses, labs)

    def _build_prompt(self, patient, ai_ml_report, llm_analysis, vitals, diagnoses, labs) -> str:
        risk = ai_ml_report.get("risk_assessment", {})
        latest_vitals = vitals[-1] if vitals else {}

        dx_names = [d.get("condition_name", "") for d in diagnoses[:5]] if diagnoses else []
        age = "unknown"
        if patient.get("date_of_birth"):
            try:
                dob = datetime.fromisoformat(str(patient["date_of_birth"]).replace("Z", ""))
                age = int((datetime.utcnow() - dob).days / 365)
            except Exception:
                pass

        guidelines_summary = (
            "RISK CLASSIFICATION:\n"
            "- 🟢 0-40%: Stable — standard monitoring\n"
            "- 🟡 41-70%: Moderate Risk (Requires Monitoring) — physician review\n"
            "- 🔴 71-100%: Critical (Immediate Attention Required)\n\n"
            "REGULATORY COMPLIANCE:\n"
            "- HIPAA: de-identify PHI, encrypt at rest/transit, breach notification\n"
            "- GDPR: lawful basis for processing, DPIA, 72h breach notification\n"
            "- FDA/CE: SaMD classification, analytical + clinical validation required\n"
            "- ISO 14971: risk management for AI-specific hazards (drift, bias, cyberattack)\n\n"
            "VALIDATION:\n"
            "- ROC AUC, sensitivity, specificity on held-out test sets\n"
            "- Subgroup analysis for bias across age, sex, ethnicity\n"
            "- Explainability required (SHAP/LIME) — must show contributing factors\n\n"
            "AI TRANSPARENCY RULES:\n"
            "- Must explain contributing factors and contradictions\n"
            "- Must flag low confidence (<75%)\n"
            "- Moderate and Critical risk requires physician review\n\n"
            "GEN AI BOUNDARIES:\n"
            "- Must NOT invent clinical data or override physician judgment\n"
            "- Must acknowledge uncertainty and cite evidence level\n"
            "- Must identify as AI-generated content\n"
            "- Human-in-the-loop: AI is an advisor, not an authority"
        )

        return f"""GROUND TRUTH VALIDATION REQUEST

PATIENT: {patient.get('full_name', 'Unknown')}, Age: {age}, Gender: {patient.get('gender', 'Unknown')}
Latest Vitals: HR={latest_vitals.get('heart_rate')} bpm, BP={latest_vitals.get('systolic_bp')}/{latest_vitals.get('diastolic_bp')} mmHg, SpO2={latest_vitals.get('oxygen_saturation')}%, Temp={latest_vitals.get('temperature')}°C
Diagnoses: {', '.join(dx_names) if dx_names else 'None recorded'}

=== AI/ML MODEL REPORT ===
Risk Score: {risk.get('risk_score', 'N/A')}
Risk Level: {risk.get('risk_level', 'N/A')}
Confidence: {risk.get('confidence_score', 'N/A')}
Contributing Factors: {risk.get('contributing_factors', {})}
Recommendations: {risk.get('recommendations', [])}
Contradictions: {risk.get('contradictions', [])}

=== LLM ANALYSIS ===
{llm_analysis}

=== CLINICAL GUIDELINES ===
{guidelines_summary}

INSTRUCTIONS:
1. Validate the AI/ML risk assessment against clinical guidelines
2. Assess the LLM analysis quality and correctness
3. Identify any discrepancies between AI findings and expected clinical reality
4. Provide corrected recommendations if needed
5. Cite specific guidelines for each recommendation
6. Rate accuracy of AI/ML report (0.0-1.0)
7. Rate quality of LLM reasoning (0.0-1.0)
8. Provide overall confidence in the ground truth (0.0-1.0)

Respond in this exact JSON structure:
{{
    "ground_truth_summary": "3-4 sentence clinical reality assessment",
    "ai_ml_report_accuracy": 0.0-1.0,
    "llm_reasoning_quality": 0.0-1.0,
    "overall_confidence": 0.0-1.0,
    "discrepancies_found": ["list of discrepancies"],
    "corrected_recommendations": ["list of corrected evidence-based recommendations"],
    "guideline_citations": ["list of specific guideline citations"]
}}"""

    def _parse_llm_response(self, text: str, ai_ml_report: dict) -> GroundTruthOutput:
        import json, re
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            logger.warning("[GenAI] Failed to parse LLM response as JSON, using fallback")
            return self._rule_based_ground_truth({}, ai_ml_report, "", [], [], [])

        return GroundTruthOutput(
            ground_truth_summary=data.get("ground_truth_summary", "Ground truth assessment completed."),
            validation_against_guidelines={},
            ai_ml_report_accuracy=float(data.get("ai_ml_report_accuracy", 0.5)),
            llm_reasoning_quality=float(data.get("llm_reasoning_quality", 0.5)),
            overall_confidence=float(data.get("overall_confidence", 0.5)),
            discrepancies_found=data.get("discrepancies_found", []),
            corrected_recommendations=data.get("corrected_recommendations", []),
            guideline_citations=data.get("guideline_citations", []),
        )

    def _rule_based_ground_truth(
        self, patient, ai_ml_report, llm_analysis, vitals, diagnoses, labs
    ) -> GroundTruthOutput:
        risk = ai_ml_report.get("risk_assessment", {})
        risk_level = risk.get("risk_level", "unknown")
        confidence = risk.get("confidence_score", 0.0)
        risk_score = risk.get("risk_score", 0.0)
        explanations = risk.get("explanation", [])
        recommendations = risk.get("recommendations", [])

        compliance = check_guideline_compliance(risk_level, confidence)

        discrepancies = []
        corrected_recs = list(recommendations)
        guideline_citations = []

        if confidence < 0.75:
            discrepancies.append("Low AI confidence — ground truth uncertain")
            guideline_citations.append("AI Transparency: confidence must exceed 75% threshold")

        if risk_level in ("critical", "moderate", "high"):
            discrepancies.append(f"{risk_level.upper()} risk flagged — requires physician validation")
            guideline_citations.append("Human-in-the-loop: moderate/critical risk requires physician review")
            if "Immediate clinical assessment required" not in str(recommendations):
                corrected_recs.insert(0, "Immediate clinical assessment required (guideline-mandated)")

        if not explanations:
            discrepancies.append("AI/ML report lacks explanation — transparency requirement not met")
            guideline_citations.append("AI Transparency: explanations must include contributing factors")

        has_abnormal = False
        for v in vitals:
            for key in ("heart_rate", "temperature", "oxygen_saturation", "systolic_bp"):
                val = v.get(key)
                if val is not None:
                    bounds = {"heart_rate": (40, 150), "temperature": (35, 40),
                              "oxygen_saturation": (85, 100), "systolic_bp": (70, 200)}.get(key)
                    if bounds and (val < bounds[0] or val > bounds[1]):
                        has_abnormal = True
                        discrepancies.append(f"Abnormal {key}={val} — not fully addressed in AI report")
                        guideline_citations.append(f"Safety boundary: {key} outside critical range")

        accuracy = max(0.2, min(1.0, confidence * (0.9 if has_abnormal else 1.0)))
        llm_quality = 0.5 if not llm_analysis else 0.7
        overall = (accuracy * 0.4 + llm_quality * 0.3 + (1.0 if not discrepancies else 0.5) * 0.3)

        if risk_level in ("stable", "low"):
            summary = (
                f"Patient presents with {risk_level.upper()} risk profile (score: {risk_score:.2f}). "
                f"AI/ML findings are generally consistent with expected clinical presentation. "
                f"No critical guideline violations detected. "
                f"{'Discrepancies noted: ' + '; '.join(discrepancies[:2]) if discrepancies else 'All findings within expected parameters.'}"
            )
        else:
            summary = (
                f"Patient presents with {risk_level.upper()} risk profile (score: {risk_score:.2f}). "
                f"AI/ML assessment flags serious concerns that require immediate physician evaluation. "
                f"Guideline compliance check indicates {len(discrepancies)} area(s) requiring attention. "
                f"Ground truth confidence is limited — physician must validate all findings."
            )

        return GroundTruthOutput(
            ground_truth_summary=summary,
            validation_against_guidelines=compliance,
            ai_ml_report_accuracy=round(accuracy, 4),
            llm_reasoning_quality=round(llm_quality, 4),
            overall_confidence=round(overall, 4),
            discrepancies_found=discrepancies,
            corrected_recommendations=corrected_recs,
            guideline_citations=guideline_citations,
        )


_genai_engine: Optional[GenAIGroundTruthEngine] = None


def get_genai_engine() -> GenAIGroundTruthEngine:
    global _genai_engine
    if _genai_engine is None:
        _genai_engine = GenAIGroundTruthEngine()
    return _genai_engine
