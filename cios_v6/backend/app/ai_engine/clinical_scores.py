"""
MEWS (Modified Early Warning Score) and NEWS2 (National Early Warning Score 2)
implementation. These are clinically validated vital sign scoring systems used
worldwide to detect patient deterioration.
"""
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class EarlyWarningScore:
    total_score: int
    risk_level: str           # low, low_medium, medium, high
    clinical_response: str    # e.g. "hourly monitoring", "urgent review"
    score_components: Dict[str, int]
    system: str               # "mews" or "news2"


MEWS_RANGES = {
    "heart_rate": [
        (0, 50, 3), (51, 60, 1), (61, 100, 0), (101, 110, 1),
        (111, 129, 2), (130, 300, 3),
    ],
    "systolic_bp": [
        (0, 70, 3), (71, 80, 2), (81, 100, 1), (101, 199, 0),
        (200, 300, 2),
    ],
    "respiratory_rate": [
        (0, 8, 3), (9, 14, 0), (15, 20, 1), (21, 29, 2),
        (30, 80, 3),
    ],
    "temperature": [
        (0, 35.0, 2), (35.1, 36.0, 1), (36.1, 38.0, 0),
        (38.1, 38.5, 1), (38.6, 42.0, 2),
    ],
    "gcs_score": [
        (3, 12, 3), (13, 14, 1), (15, 15, 0),
    ],
}

NEWS2_RANGES = {
    "heart_rate": [
        (0, 40, 3), (41, 50, 1), (51, 90, 0), (91, 110, 1),
        (111, 130, 2), (131, 300, 3),
    ],
    "systolic_bp": [
        (0, 90, 3), (91, 100, 2), (101, 110, 1), (111, 219, 0),
        (220, 300, 3),
    ],
    "respiratory_rate": [
        (0, 8, 3), (9, 11, 1), (12, 20, 0), (21, 24, 2),
        (25, 80, 3),
    ],
    "temperature": [
        (0, 35.0, 3), (35.1, 36.0, 1), (36.1, 38.0, 0),
        (38.1, 39.0, 1), (39.1, 42.0, 2),
    ],
    "oxygen_saturation": [
        (0, 91, 3), (92, 93, 2), (94, 95, 1), (96, 100, 0),
    ],
    "gcs_score": [
        (3, 14, 3), (15, 15, 0),
    ],
}

NEWS2_SCALE2 = {
    "oxygen_saturation": [
        (0, 83, 3), (84, 85, 2), (86, 87, 1), (88, 100, 0),
    ],
}

CLINICAL_RESPONSE = {
    "mews": {
        (0, 2): ("low", "Standard monitoring — every 4-6 hours"),
        (3, 4): ("low_medium", "Increase monitoring — every 2-4 hours, notify RN"),
        (5, 6): ("medium", "Urgent review — notify physician within 30 min"),
        (7, 14): ("high", "Immediate review — emergency response required"),
    },
    "news2": {
        (0, 4): ("low", "Standard monitoring — minimum every 6 hours"),
        (5, 6): ("low_medium", "Ward-based response — increase monitoring to 4-hourly"),
        (7, 8): ("medium", "Urgent response — physician review within 1 hour"),
        (9, 20): ("high", "Emergency response — immediate clinical review"),
    },
}


def _score_for_value(ranges, value) -> int:
    if value is None:
        return 0
    for low, high, score in ranges:
        if low <= value <= high:
            return score
    return 0


def _assign_clinical_response(system: str, total: int) -> Tuple[str, str]:
    mapping = CLINICAL_RESPONSE.get(system, {})
    for (low, high), (level, response) in sorted(mapping.items()):
        if low <= total <= high:
            return level, response
    return ("high", "Immediate emergency response")


def compute_mews(vitals: Dict, use_scale2: bool = False) -> EarlyWarningScore:
    score = {}
    ranges = NEWS2_SCALE2 if use_scale2 else NEWS2_RANGES

    for vital, _ in MEWS_RANGES.items():
        if vital == "oxygen_saturation":
            val = vitals.get("oxygen_saturation")
            score[vital] = _score_for_value(ranges.get(vital, []), val)
        else:
            val = vitals.get(vital)
            score[vital] = _score_for_value(MEWS_RANGES.get(vital, []), val)

    total = sum(score.values())
    level, response = _assign_clinical_response("mews", total)

    return EarlyWarningScore(
        total_score=total,
        risk_level=level,
        clinical_response=response,
        score_components=score,
        system="mews",
    )


def compute_news2(vitals: Dict, on_supplemental_o2: bool = False) -> EarlyWarningScore:
    score = {}
    ranges = NEWS2_SCALE2 if on_supplemental_o2 else NEWS2_RANGES

    for vital, range_list in NEWS2_RANGES.items():
        val = vitals.get(vital)
        score[vital] = _score_for_value(range_list, val)

    total = sum(score.values())

    if on_supplemental_o2:
        total += 2

    level, response = _assign_clinical_response("news2", total)

    return EarlyWarningScore(
        total_score=total,
        risk_level=level,
        clinical_response=response,
        score_components=score,
        system="news2",
    )


def compute_both(vitals: Dict, on_supplemental_o2: bool = False) -> List[EarlyWarningScore]:
    return [
        compute_mews(vitals),
        compute_news2(vitals, on_supplemental_o2),
    ]
