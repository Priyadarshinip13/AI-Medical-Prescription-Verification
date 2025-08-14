# backend/app/main.py
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.services import ocr, extract, interactions
from app.schemas import ExtractionResponse, ValidationResult, MedLine, PatientContext
from typing import List
import io
from app.db import SessionLocal, PrescriptionHistory

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Rx Safety API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# You can centralize dose rules in services/dose_rules.py and interactions module uses them
# For now we rely on interactions.check_interactions & interactions.suggest_alternatives_for_flagged

@app.post("/extract", response_model=ExtractionResponse)
async def route_extract(file: UploadFile = File(None), text: str = Form(None)):
    try:
        raw_text = ""

        # Handle file upload
        if file:
            try:
                content = await file.read()
                raw_text = ocr.image_bytes_to_text(content) or ""
            except Exception as e:
                log.error(f"OCR failed: {e}")
                return ExtractionResponse(meds=[], error=f"OCR failed: {str(e)}")

        # Handle pasted text
        elif text:
            raw_text = text.strip()

        # No input
        else:
            return ExtractionResponse(meds=[], error="No file or text provided.")

        # Parse meds
        try:
            meds = extract.simple_parse_lines(raw_text)
        except Exception as e:
            log.error(f"Parsing failed: {e}")
            return ExtractionResponse(meds=[], error=f"Parsing failed: {str(e)}")

        return ExtractionResponse(meds=meds)

    except Exception as e:
        log.exception("Unexpected error in /extract")
        return ExtractionResponse(meds=[], error=f"Internal error: {str(e)}")


@app.post("/analyze", response_model=ValidationResult)
async def route_analyze(payload: dict):
    """
    payload example:
    {
      "patient": {"name": "Jane Doe", "age_years": 45, "weight_kg": 60, "egfr": 90, "allergies": []},
      "meds": [ { medline dicts } ]
    }
    """
    try:
        patient = PatientContext(**payload.get("patient", {}))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid patient payload: {e}")

    meds_in = payload.get("meds", [])
    meds = [MedLine(**m) for m in meds_in]

    # 1) Interaction checking (should return list of dicts)
    inter = interactions.check_interactions(meds, patient.dict())

    # 2) Dose issues using interactions/dose rules module (implement realistic rules there)
    dose_issues = []
    # Example: use interactions.check_dose or a local rules engine if available
    # But provide a real-ish fallback here:
    for m in meds:
        drug_name = (m.drug or "").lower()
        daily_dose = (m.strength or 0) * (m.frequency_per_day or 1)
        # ask interactions module if it exposes a dose check helper
        try:
            if hasattr(interactions, "check_dose_for_med"):
                di = interactions.check_dose_for_med(m, patient.dict())
                if di:
                    dose_issues.extend(di if isinstance(di, list) else [di])
            else:
                # fallback: some basic rules (simplified)
                if drug_name == "simvastatin" and daily_dose >= 80:
                    dose_issues.append({"drug": m.drug, "level": "high",
                                        "message": f"{m.drug} {daily_dose} mg/day: high myopathy risk; consider lower dose."})
                if drug_name == "warfarin" and daily_dose > 10:
                    dose_issues.append({"drug": m.drug, "level": "high",
                                        "message": f"{m.drug} total {daily_dose} mg/day — high bleeding risk; check INR."})
                if drug_name == "ibuprofen":
                    # renal flag example
                    if patient.egfr is not None and patient.egfr < 60 and daily_dose > 1200:
                        dose_issues.append({"drug": m.drug, "level": "warning",
                                            "message": f"Ibuprofen {daily_dose} mg/day in reduced eGFR ({patient.egfr}) — avoid high doses."})
        except Exception as e:
            log.warning("Dose check helper failed: %s", e)

    # 3) Alternatives
    alts = interactions.suggest_alternatives_for_flagged(meds, inter, patient.dict())

    # 4) Save to DB
    db = SessionLocal()
    try:
        record = PrescriptionHistory(
            patient_name=(payload.get("patient") or {}).get("name") or "Unknown",
            patient_age=patient.age_years,
            patient_weight=patient.weight_kg,
            patient_egfr=patient.egfr,
            allergies=",".join(payload.get("patient", {}).get("allergies", []) or []),
            meds=[m.dict() for m in meds],
            dose_issues=dose_issues,
            interactions=inter,
            alternatives=alts
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        log.error("Failed to save history: %s", e)
    finally:
        db.close()

    return ValidationResult(dose_issues=dose_issues, interactions=inter, alternatives=alts)


@app.get("/history/{patient_name}")
def get_patient_history(patient_name: str, limit: int = 50):
    """
    Returns recent analysis records for a given patient_name (case-insensitive).
    """
    db = SessionLocal()
    try:
        q = db.query(PrescriptionHistory).filter(PrescriptionHistory.patient_name.ilike(f"%{patient_name}%")).order_by(PrescriptionHistory.created_at.desc()).limit(limit)
        results = []
        for r in q:
            results.append({
                "id": r.id,
                "date": r.created_at.isoformat(),
                "patient_name": r.patient_name,
                "patient_age": r.patient_age,
                "patient_weight": r.patient_weight,
                "patient_egfr": r.patient_egfr,
                "allergies": r.allergies,
                "meds": r.meds,
                "dose_issues": r.dose_issues,
                "interactions": r.interactions,
                "alternatives": r.alternatives
            })
        return results
    finally:
        db.close()


@app.get("/history")
def list_history(limit: int = 50):
    """List recent analyses across all patients"""
    db = SessionLocal()
    try:
        q = db.query(PrescriptionHistory).order_by(PrescriptionHistory.created_at.desc()).limit(limit)
        return [{
            "id": r.id,
            "date": r.created_at.isoformat(),
            "patient_name": r.patient_name,
            "meds": r.meds,
            "dose_issues": r.dose_issues,
            "interactions": r.interactions,
            "alternatives": r.alternatives
        } for r in q]
    finally:
        db.close()
