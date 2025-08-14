# backend/app/services/normalize.py
import requests

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"

def rxnorm_lookup(name: str):
    """
    Lookup RxCUI for a drug name using the public RxNorm REST API.
    Returns first rxcui as string or None.
    """
    if not name:
        return None
    try:
        params = {"name": name, "search": 1}
        r = requests.get(f"{RXNORM_BASE}/rxcui.json", params=params, timeout=5)
        r.raise_for_status()
        j = r.json()
        ids = j.get("idGroup", {}).get("rxnormId", [])
        if ids:
            return ids[0]
    except Exception:
        return None
    return None

def normalize_strength_unit(strength, unit):
    """
    Basic normalization of strength units. Returns (float strength, canonical unit).
    """
    if strength is None:
        return None, None
    if not unit:
        return strength, None
    unit = unit.lower()
    try:
        if unit in ("mg",):
            return float(strength), "mg"
        if unit in ("g",):
            return float(strength) * 1000.0, "mg"
        if unit in ("mcg", "µg", "ug"):
            return float(strength) / 1000.0, "mg"
        if unit.lower() in ("ml","mL"):
            return float(strength), "ml"
    except Exception:
        pass
    return float(strength), unit
