# backend/app/services/extract.py
import re
from typing import List
from app.schemas import MedLine

# Optional: Hugging Face medical NER
try:
    from transformers import pipeline
    ner_pipe = pipeline("ner", model="d4data/biomedical-ner-all", aggregation_strategy="simple")
except Exception:
    ner_pipe = None

# Common medical abbreviations for dosage frequency
FREQ_ABBREV_MAP = {
    "od": 1,   # once daily
    "bd": 2,   # twice daily
    "tds": 3,  # three times daily
    "tid": 3,  # three times daily
    "qid": 4,  # four times daily
    "hs": 1,   # at bedtime (once daily)
    "prn": None,  # as needed, leave None for frequency
}

def clean_ocr_text(text: str) -> str:
    """Clean and normalize OCR text."""
    text = re.sub(r"[^a-zA-Z0-9\s\.\,\/\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def regex_parse(text: str) -> List[dict]:
    """
    Extract meds with regex and decode frequency abbreviations.
    """
    meds = []
    # Match patterns like "Amoxicillin 500 mg BD" or "Paracetamol 650mg TDS"
    pattern = re.compile(
        r"([A-Za-z]+(?:\s[A-Za-z]+)*)\s+(\d+)\s*(mg|g|mcg)\s*([A-Za-z0-9]+)?",
        re.IGNORECASE
    )

    for match in pattern.finditer(text):
        name = match.group(1).strip()
        strength = int(match.group(2))
        unit = match.group(3).lower()
        freq_str = (match.group(4) or "").lower()

        # Decode abbreviation if in map
        frequency = None
        if freq_str in FREQ_ABBREV_MAP:
            frequency = FREQ_ABBREV_MAP[freq_str]
        elif freq_str.endswith("x"):  # e.g., "3x"
            try:
                frequency = int(freq_str.replace("x", ""))
            except ValueError:
                frequency = None

        meds.append({
            "name": name,
            "strength": strength,
            "unit": unit,
            "frequency_per_day": frequency,
            "route": "oral"
        })
    return meds

def ner_parse(text: str) -> List[dict]:
    """Fallback to Hugging Face NER."""
    if not ner_pipe:
        return []
    entities = ner_pipe(text)
    meds = []
    for ent in entities:
        if ent['entity_group'] in ["CHEMICAL", "DRUG"]:
            meds.append({
                "name": ent['word'],
                "strength": None,
                "unit": None,
                "frequency_per_day": None,
                "route": None
            })
    return meds

def simple_parse_lines(raw_text: str) -> List[MedLine]:
    """
    Main extraction entry point.
    """
    text = clean_ocr_text(raw_text)
    meds = regex_parse(text)
    if not meds:
        meds = ner_parse(text)
    return [MedLine(**m) for m in meds]
