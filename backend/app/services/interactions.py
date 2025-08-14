# backend/app/services/interactions.py
import json
import os
from typing import List, Dict, Any
from app.schemas import InteractionPair, MedLine
import logging

log = logging.getLogger("interactions")

HERE = os.path.dirname(__file__)
DATA_PATH = os.path.join(HERE, "..", "data", "mock_interactions.json")

# try load, else empty dict
try:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        INTERACTIONS_DB = json.load(f)
except Exception:
    INTERACTIONS_DB = {}

def lookup_interaction(a_rxcui: str, b_rxcui: str):
    if not a_rxcui or not b_rxcui:
        return None
    key1 = f"{a_rxcui}|{b_rxcui}"
    key2 = f"{b_rxcui}|{a_rxcui}"
    return INTERACTIONS_DB.get(key1) or INTERACTIONS_DB.get(key2)

def check_interactions(meds: List[MedLine], patient: Dict[str, Any]) -> List[InteractionPair]:
    results = []
    seen = set()
    for i in range(len(meds)):
        for j in range(i+1, len(meds)):
            a = meds[i]
            b = meds[j]
            rec = lookup_interaction(a.rxcui, b.rxcui)
            if rec:
                severity = rec.get("severity", "moderate")
                ip = InteractionPair(
                    a_rxcui=a.rxcui or a.drug or "unknown",
                    b_rxcui=b.rxcui or b.drug or "unknown",
                    severity=severity,
                    mechanism=rec.get("mechanism"),
                    management=rec.get("management")
                )
                key = tuple(sorted([ip.a_rxcui, ip.b_rxcui, severity]))
                if key not in seen:
                    results.append(ip)
                    seen.add(key)
    return results

def suggest_alternatives_for_flagged(meds, interactions, patient):
    ALTS = {
        "83367": [{"rxcui": "5555", "name": "Pravastatin"}],
    }
    flagged = set()
    for p in interactions:
        if p.severity in ("major", "contraindicated", "contra"):
            flagged.add(p.a_rxcui)
            flagged.add(p.b_rxcui)

    recs = []
    for m in meds:
        if m.rxcui in flagged:
            alts = ALTS.get(m.rxcui, [])
            for a in alts:
                nm = MedLine(raw=str(a.get("name")), drug=a.get("name"), rxcui=a.get("rxcui"))
                recs.append(nm)
    return recs
