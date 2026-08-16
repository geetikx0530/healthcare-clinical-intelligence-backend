import re
from typing import Dict, Any, List, Optional

COMMON_DRUG_NAMES = [
    "albuterol", "fluticasone", "amoxicillin", "lisinopril", "metformin",
    "aspirin", "ibuprofen", "paracetamol", "acetaminophen", "atorvastatin",
    "omeprazole", "prednisone", "azithromycin", "levothyroxine", "amlodipine",
    "metoprolol", "losartan", "gabapentin", "hydrochlorothiazide", "sertraline",
    "simvastatin", "montelukast", "furosemide", "pantoprazole", "ciprofloxacin"
]

COMMON_SYMPTOMS = [
    "shortness of breath", "persistent cough", "cough", "fever", "chills",
    "chest pain", "headache", "nausea", "vomiting", "diarrhea", "fatigue",
    "dizziness", "sore throat", "wheezing", "joint pain", "back pain",
    "rash", "swelling", "abdominal pain", "nasal congestion", "runny nose"
]

COMMON_DIAGNOSES = [
    "asthma", "asthma exacerbation", "bronchitis", "acute bronchitis",
    "hypertension", "type 2 diabetes", "diabetes", "pneumonia", "allergies",
    "seasonal allergies", "covid-19", "influenza", "migraine", "gastritis",
    "anemia", "sinusitis", "pharyngitis", "otitis media", "copd", "gerd"
]

DOSAGE_PATTERN = re.compile(
    r'\b\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|units|puffs?|tablets?|capsules?|mg/dl|mmhg|bpm)\b',
    re.IGNORECASE
)

FREQUENCY_PATTERN = re.compile(
    r'\b(?:every\s+\d+(?:\s*to\s*\d+)?\s*hours?|twice\s+daily|once\s+daily|three\s+times\s+daily|daily|as\s+needed|at\s+bedtime)\b',
    re.IGNORECASE
)


def _split_into_sections(text: str) -> Dict[str, List[str]]:
    """
    Splits clinical text into sections based on standard medical section headers.
    """
    section_headers = [
        ("chief_complaint", [r"chief complaint", r"symptoms", r"presentation", r"complaint"]),
        ("diagnosis", [r"diagnosis", r"assessment", r"impression", r"clinical diagnosis", r"condition"]),
        ("medications", [r"medications", r"prescription", r"rx", r"prescribed medications"]),
        ("treatment_plan", [r"treatment plan", r"treatment", r"plan", r"recommendations?", r"instructions"]),
        ("clinical_findings", [r"clinical findings", r"findings", r"physical exam", r"vitals", r"lab results", r"examination"])
    ]

    lines = text.splitlines()
    sections: Dict[str, List[str]] = {
        "chief_complaint": [],
        "diagnosis": [],
        "medications": [],
        "treatment_plan": [],
        "clinical_findings": [],
        "general": []
    }

    current_section = "general"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        header_found = False
        lower_line = stripped.lower()
        clean_header = lower_line.rstrip(":")

        for sec_key, patterns in section_headers:
            for pat in patterns:
                if clean_header == pat or lower_line.startswith(pat + ":") or lower_line.startswith(pat + " -"):
                    current_section = sec_key
                    header_found = True
                    after_colon = line.split(":", 1)
                    if len(after_colon) > 1 and after_colon[1].strip():
                        sections[current_section].append(after_colon[1].strip())
                    break
            if header_found:
                break

        if not header_found:
            sections[current_section].append(stripped)

    return sections


def extract_medical_entities(text: Optional[str]) -> Dict[str, Any]:
    """
    Extracts structured medical entities (symptoms, diagnoses, medications,
    dosages, treatment plans, medical conditions, clinical findings) from OCR raw_text.
    Handles empty/missing text gracefully.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return {
            "symptoms": [],
            "diagnoses": [],
            "medications": [],
            "dosages": [],
            "treatment_plans": [],
            "medical_conditions": [],
            "important_clinical_findings": [],
            "entities": []
        }

    cleaned_text = text.strip()
    sections = _split_into_sections(cleaned_text)

    symptoms_list: List[str] = []
    diagnoses_list: List[str] = []
    medications_list: List[str] = []
    dosages_list: List[str] = []
    treatment_plans_list: List[str] = []
    medical_conditions_list: List[str] = []
    clinical_findings_list: List[str] = []

    # 1. Process Symptoms / Chief Complaint Section
    if sections["chief_complaint"]:
        for item in sections["chief_complaint"]:
            item_clean = item.strip("- *").strip()
            if item_clean:
                symptoms_list.append(item_clean)

    # Keyword check for symptoms across full text
    lower_text = cleaned_text.lower()
    for sym in COMMON_SYMPTOMS:
        if sym in lower_text:
            if not any(sym in s.lower() for s in symptoms_list):
                symptoms_list.append(sym.title())

    # 2. Process Diagnosis & Medical Conditions Section
    if sections["diagnosis"]:
        for item in sections["diagnosis"]:
            item_clean = item.strip("- *").strip()
            if item_clean:
                diagnoses_list.append(item_clean)
                medical_conditions_list.append(item_clean)

    for diag in COMMON_DIAGNOSES:
        if diag in lower_text:
            if not any(diag in d.lower() for d in diagnoses_list):
                diagnoses_list.append(diag.title())
            if not any(diag in c.lower() for c in medical_conditions_list):
                medical_conditions_list.append(diag.title())

    # 3. Process Medications Section & Dosages
    if sections["medications"]:
        for item in sections["medications"]:
            item_clean = item.strip("- *").strip()
            if item_clean:
                medications_list.append(item_clean)

    for line in cleaned_text.splitlines():
        lower_line = line.lower()
        for drug in COMMON_DRUG_NAMES:
            if drug in lower_line:
                line_clean = line.strip("- *").strip()
                if line_clean and not any(drug in m.lower() for m in medications_list):
                    medications_list.append(line_clean)

    dosages = DOSAGE_PATTERN.findall(cleaned_text)
    for d in dosages:
        if d not in dosages_list:
            dosages_list.append(d)

    freqs = FREQUENCY_PATTERN.findall(cleaned_text)
    for f in freqs:
        if f not in dosages_list:
            dosages_list.append(f)

    # 4. Process Treatment Plan Section
    if sections["treatment_plan"]:
        for item in sections["treatment_plan"]:
            item_clean = item.strip("- *").strip()
            if item_clean:
                treatment_plans_list.append(item_clean)

    for line in cleaned_text.splitlines():
        line_clean = line.strip("- *").strip()
        lower_l = line_clean.lower()
        if any(w in lower_l for w in ["inhaler", "take ", "tablets", "puffs", "daily", "follow up", "mg", "twice"]):
            if line_clean and not any(line_clean == tp for tp in treatment_plans_list):
                if not line_clean.endswith(":") and len(line_clean) > 5:
                    treatment_plans_list.append(line_clean)

    # 5. Process Clinical Findings Section
    if sections["clinical_findings"]:
        for item in sections["clinical_findings"]:
            item_clean = item.strip("- *").strip()
            if item_clean:
                clinical_findings_list.append(item_clean)

    if not clinical_findings_list and symptoms_list:
        clinical_findings_list = [s for s in symptoms_list]

    def _dedupe(seq: List[str]) -> List[str]:
        seen = set()
        res = []
        for x in seq:
            clean_x = x.strip()
            if clean_x and clean_x.lower() not in seen:
                seen.add(clean_x.lower())
                res.append(clean_x)
        return res

    symptoms_list = _dedupe(symptoms_list)
    diagnoses_list = _dedupe(diagnoses_list)
    medications_list = _dedupe(medications_list)
    dosages_list = _dedupe(dosages_list)
    treatment_plans_list = _dedupe(treatment_plans_list)
    medical_conditions_list = _dedupe(medical_conditions_list)
    clinical_findings_list = _dedupe(clinical_findings_list)

    entities: List[Dict[str, Any]] = []

    for sym in symptoms_list:
        entities.append({"entity_type": "SYMPTOM", "entity_text": sym, "confidence": 0.90})

    for diag in diagnoses_list:
        entities.append({"entity_type": "DIAGNOSIS", "entity_text": diag, "confidence": 0.95})

    for med in medications_list:
        entities.append({"entity_type": "MEDICATION", "entity_text": med, "confidence": 0.95})

    for dos in dosages_list:
        entities.append({"entity_type": "DOSAGE", "entity_text": dos, "confidence": 0.90})

    for tp in treatment_plans_list:
        entities.append({"entity_type": "TREATMENT_PLAN", "entity_text": tp, "confidence": 0.85})

    return {
        "symptoms": symptoms_list,
        "diagnoses": diagnoses_list,
        "medications": medications_list,
        "dosages": dosages_list,
        "treatment_plans": treatment_plans_list,
        "medical_conditions": medical_conditions_list,
        "important_clinical_findings": clinical_findings_list,
        "entities": entities
    }
