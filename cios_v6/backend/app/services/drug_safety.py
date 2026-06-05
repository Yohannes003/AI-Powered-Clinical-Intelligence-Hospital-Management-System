"""
Drug Safety Engine — drug-drug interaction checking and allergy cross-referencing.
Uses a built-in interaction database with RxNorm-style drug names.
In production, replace with a call to a real drug DB (RxNav, OpenFDA, or commercial).
"""
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum


class InteractionSeverity(str, Enum):
    CONTRAINDICATED = "contraindicated"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"


class AllergyReaction(str, Enum):
    ANAPHYLAXIS = "anaphylaxis"
    ANGIOEDEMA = "angioedema"
    RASH = "rash"
    HIVES = "hives"
    GI_DISTRESS = "gi_distress"
    RESPIRATORY = "respiratory"
    OTHER = "other"


@dataclass
class InteractionResult:
    drug_a: str
    drug_b: str
    severity: InteractionSeverity
    description: str
    recommendation: str


@dataclass
class AllergyCrossMatch:
    drug: str
    allergen: str
    reaction_type: AllergyReaction
    severity: str
    description: str


@dataclass
class DrugSafetyReport:
    drug_name: str
    drug_class: str
    interactions: List[InteractionResult] = field(default_factory=list)
    allergies: List[AllergyCrossMatch] = field(default_factory=list)
    duplicates: List[str] = field(default_factory=list)
    is_safe: bool = True
    summary: str = ""


DRUG_CLASSES = {
    "antibiotic": {
        "penicillin", "amoxicillin", "ampicillin", "piperacillin", "cefalexin",
        "ceftriaxone", "cefepime", "meropenem", "azithromycin", "clarithromycin",
        "erythromycin", "ciprofloxacin", "levofloxacin", "moxifloxacin",
        "doxycycline", "vancomycin", "clindamycin", "metronidazole",
    },
    "nsaid": {
        "ibuprofen", "naproxen", "diclofenac", "ketorolac", "indomethacin",
        "meloxicam", "celecoxib", "aspirin",
    },
    "anticoagulant": {
        "warfarin", "heparin", "enoxaparin", "rivaroxaban", "apixaban",
        "dabigatran", "edoxaban",
    },
    "antihypertensive": {
        "lisinopril", "enalapril", "ramipril", "losartan", "valsartan",
        "metoprolol", "atenolol", "propranolol", "amlodipine", "nifedipine",
        "hydrochlorothiazide", "furosemide", "spironolactone",
    },
    "opioid": {
        "morphine", "fentanyl", "hydromorphone", "oxycodone", "codeine",
        "tramadol", "methadone",
    },
    "antidiabetic": {
        "metformin", "insulin", "glipizide", "glyburide", "sitagliptin",
        "empagliflozin", "liraglutide",
    },
    "psychiatric": {
        "sertraline", "fluoxetine", "citalopram", "escitalopram", "paroxetine",
        "haloperidol", "olanzapine", "quetiapine", "risperidone", "lithium",
    },
    "corticosteroid": {
        "prednisone", "dexamethasone", "hydrocortisone", "methylprednisolone",
        "budesonide",
    },
}

KNOWN_INTERACTIONS = [
    InteractionResult(
        "warfarin", "aspirin", InteractionSeverity.MAJOR,
        "Increased risk of bleeding when warfarin is combined with aspirin",
        "Monitor INR closely; consider alternative analgesia. Avoid combination if possible."
    ),
    InteractionResult(
        "warfarin", "ibuprofen", InteractionSeverity.MAJOR,
        "NSAIDs increase warfarin's anticoagulant effect and GI bleed risk",
        "Prefer acetaminophen for analgesia. If NSAID required, monitor INR within 3-5 days."
    ),
    InteractionResult(
        "lisinopril", "spironolactone", InteractionSeverity.MODERATE,
        "Combination increases risk of hyperkalemia",
        "Monitor serum potassium within 1 week of starting combination."
    ),
    InteractionResult(
        "metformin", "contrast_dye", InteractionSeverity.MAJOR,
        "Metformin + iodinated contrast increases risk of lactic acidosis in renal impairment",
        "Hold metformin 48h before and after contrast procedure; check renal function."
    ),
    InteractionResult(
        "ciprofloxacin", "warfarin", InteractionSeverity.MAJOR,
        "Fluoroquinolones potentiate warfarin effect — increased INR and bleeding risk",
        "Monitor INR every 2-3 days during antibiotic course."
    ),
    InteractionResult(
        "simvastatin", "clarithromycin", InteractionSeverity.CONTRAINDICATED,
        "Clarithromycin dramatically increases statin levels — rhabdomyolysis risk",
        "Avoid combination. Use azithromycin instead, or hold statin during clarithromycin course."
    ),
    InteractionResult(
        "morphine", "gabapentin", InteractionSeverity.MODERATE,
        "Additive CNS depression — increased risk of respiratory depression and sedation",
        "Reduce doses of both agents; monitor respiratory rate and sedation level."
    ),
    InteractionResult(
        "metoprolol", "verapamil", InteractionSeverity.MAJOR,
        "Combined beta-blocker and calcium channel blocker can cause bradycardia and heart block",
        "Avoid combination. If necessary, monitor ECG and heart rate closely."
    ),
    InteractionResult(
        "digoxin", "furosemide", InteractionSeverity.MODERATE,
        "Furosemide-induced hypokalemia increases digoxin toxicity risk",
        "Monitor potassium levels; maintain K+ > 4.0 mEq/L."
    ),
    InteractionResult(
        "methotrexate", "ibuprofen", InteractionSeverity.MAJOR,
        "NSAIDs reduce methotrexate clearance — severe toxicity risk",
        "Avoid NSAIDs in patients on methotrexate. Use acetaminophen instead."
    ),
    InteractionResult(
        "lithium", "ibuprofen", InteractionSeverity.MODERATE,
        "NSAIDs increase lithium levels by reducing renal clearance",
        "Monitor lithium levels within 5 days; adjust lithium dose if needed."
    ),
    InteractionResult(
        "sertraline", "tramadol", InteractionSeverity.MAJOR,
        "Increased risk of serotonin syndrome",
        "Avoid combination. Consider alternative analgesia or antidepressant."
    ),
    InteractionResult(
        "sertraline", "linezolid", InteractionSeverity.CONTRAINDICATED,
        "Linezolid is an MAOI — combined with SSRI risks serotonin syndrome",
        "Discontinue SSRI before starting linezolid, or use alternative antibiotic."
    ),
    InteractionResult(
        "theophylline", "ciprofloxacin", InteractionSeverity.MODERATE,
        "Ciprofloxacin reduces theophylline clearance — toxicity risk",
        "Monitor theophylline levels; reduce dose by 25-50% if needed."
    ),
    InteractionResult(
        "amiodarone", "warfarin", InteractionSeverity.MAJOR,
        "Amiodarone potentiates warfarin effect — significant INR increase",
        "Reduce warfarin dose by 25-50%; monitor INR twice weekly."
    ),
]

KNOWN_ALLERGENS: Dict[str, List[Tuple[str, AllergyReaction, str]]] = {
    "penicillin": [
        ("penicillins", AllergyReaction.ANAPHYLAXIS, "Risk of cross-reaction with all penicillins"),
    ],
    "amoxicillin": [
        ("penicillins", AllergyReaction.ANAPHYLAXIS, "Cross-reaction within penicillin class"),
    ],
    "cephalexin": [
        ("cephalosporins", AllergyReaction.RASH, "Mild cross-reaction risk (1-3%) with penicillins"),
    ],
    "ceftriaxone": [
        ("cephalosporins", AllergyReaction.RASH, "Cross-reaction risk with penicillins ~1-3%"),
    ],
    "aspirin": [
        ("salicylates", AllergyReaction.RESPIRATORY, "May trigger aspirin-exacerbated respiratory disease"),
        ("nsaid", AllergyReaction.HIVES, "Cross-reaction with other NSAIDs possible"),
    ],
    "ibuprofen": [
        ("nsaid", AllergyReaction.HIVES, "Cross-reaction with aspirin and other NSAIDs"),
    ],
    "sulfamethoxazole": [
        ("sulfonamides", AllergyReaction.RASH, "May cross-react with other sulfa drugs"),
    ],
    "codeine": [
        ("opioids", AllergyReaction.HIVES, "Cross-reaction with other opioids possible"),
    ],
    "morphine": [
        ("opioids", AllergyReaction.HIVES, "Cross-reaction with other opioids possible"),
    ],
    "vancomycin": [
        ("glycopeptides", AllergyReaction.OTHER, "Red man syndrome is infusion reaction, not true allergy"),
    ],
}

CROSS_CLASS_ALLERGY = [
    ("penicillins", "cephalosporins", 0.03),
    ("sulfonamides", "sulfonylureas", 0.04),
    ("nsaid", "aspirin", 0.10),
]


def _normalize_drug(name: str) -> str:
    return name.strip().lower()


def _find_drug_class(drug: str) -> Optional[str]:
    for cls_name, members in DRUG_CLASSES.items():
        if drug in members:
            return cls_name
    return None


def check_drug_interactions(
    drug_name: str,
    existing_medications: List[str],
) -> DrugSafetyReport:
    drug = _normalize_drug(drug_name)
    drug_class = _find_drug_class(drug)
    report = DrugSafetyReport(drug_name=drug_name, drug_class=drug_class or "unknown")

    seen = set()
    for existing in existing_medications:
        existing_norm = _normalize_drug(existing)
        if existing_norm == drug:
            continue
        key = tuple(sorted([drug, existing_norm]))
        if key in seen:
            continue
        seen.add(key)

        for interaction in KNOWN_INTERACTIONS:
            a = _normalize_drug(interaction.drug_a)
            b = _normalize_drug(interaction.drug_b)
            pair = {a, b}
            if {drug, existing_norm} == pair:
                report.interactions.append(interaction)

        if drug == existing_norm:
            report.duplicates.append(existing)

    if report.interactions:
        severities = {i.severity for i in report.interactions}
        if InteractionSeverity.CONTRAINDICATED in severities:
            report.is_safe = False
            report.summary = "CONTAINS CONTRAINDICATED COMBINATION"
        elif InteractionSeverity.MAJOR in severities:
            report.summary = "Contains major interaction(s) — require physician approval"
        elif InteractionSeverity.MODERATE in severities:
            report.summary = "Contains moderate interaction(s) — monitor recommended"

    if not report.summary:
        report.summary = "No significant drug interactions found"

    return report


def check_allergy_crossmatch(
    drug_name: str,
    patient_allergies: List[str],
) -> List[AllergyCrossMatch]:
    drug = _normalize_drug(drug_name)
    results = []

    for allergy in patient_allergies:
        allergy_norm = _normalize_drug(allergy)

        known = KNOWN_ALLERGENS.get(drug, [])
        for allergen, reaction, desc in known:
            if allergy_norm in allergen or allergen in allergy_norm:
                results.append(AllergyCrossMatch(
                    drug=drug_name,
                    allergen=allergy,
                    reaction_type=reaction,
                    severity="high" if reaction in (AllergyReaction.ANAPHYLAXIS, AllergyReaction.ANGIOEDEMA) else "moderate",
                    description=desc,
                ))

        drug_class = _find_drug_class(drug)
        allergy_class = _find_drug_class(allergy_norm)
        if drug_class and allergy_class:
            for cls_a, cls_b, rate in CROSS_CLASS_ALLERGY:
                if (drug_class == cls_a and allergy_class == cls_b) or \
                   (drug_class == cls_b and allergy_class == cls_a):
                    if rate > 0:
                        results.append(AllergyCrossMatch(
                            drug=drug_name,
                            allergen=allergy,
                            reaction_type=AllergyReaction.RASH,
                            severity="low",
                            description=f"Possible cross-allergy ({rate*100:.0f}% risk) between {drug_class} and {allergy_class}",
                        ))

    return results


def full_drug_safety_check(
    drug_name: str,
    existing_medications: List[str],
    patient_allergies: List[str],
) -> DrugSafetyReport:
    report = check_drug_interactions(drug_name, existing_medications)
    report.allergies = check_allergy_crossmatch(drug_name, patient_allergies)

    if report.allergies:
        has_severe = any(a.severity in ("high", "moderate") for a in report.allergies)
        if has_severe:
            report.is_safe = False
            report.summary = "ALLERGY CONTRAINDICATION — do not administer"
        elif report.summary == "No significant drug interactions found":
            report.summary = "Minor allergy match — monitor for reaction"

    return report
