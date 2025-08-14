# backend/app/schemas.py
from pydantic import BaseModel
from typing import List, Optional, Any

class PatientContext(BaseModel):
    age_years: Optional[float] = None
    weight_kg: Optional[float] = None
    egfr: Optional[float] = None
    hepatic_status: Optional[str] = None
    allergies: Optional[List[str]] = []

class MedLine(BaseModel):
    raw: str
    drug: Optional[str] = None
    rxcui: Optional[str] = None
    strength: Optional[float] = None
    unit: Optional[str] = None
    frequency: Optional[str] = None
    duration_days: Optional[int] = None
    route: Optional[str] = None
    confidence: Optional[float] = 1.0

class ExtractionResponse(BaseModel):
    meds: List[MedLine]

class InteractionPair(BaseModel):
    a_rxcui: str
    b_rxcui: str
    severity: str
    mechanism: Optional[str]
    management: Optional[str]

class ValidationResult(BaseModel):
    dose_issues: List[Any] = []
    interactions: List[InteractionPair] = []
    alternatives: List[MedLine] = []
