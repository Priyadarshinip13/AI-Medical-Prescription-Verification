# app/services/dose_rules.py

DOSE_LIMITS = {
    "warfarin": {
        "standard_max_mg_per_day": 10,
        "elderly_max_mg_per_day": 5,
        "notes": "High bleeding risk; monitor INR."
    },
    "ibuprofen": {
        "standard_max_mg_per_day": 3200,
        "renally_adjusted_max_mg_per_day": 1200,
        "eGFR_threshold": 60,
        "notes": "NSAIDs contraindicated in low eGFR."
    },
    "simvastatin": {
        "standard_max_mg_per_day": 40,
        "elderly_max_mg_per_day": 20,
        "notes": "80mg linked to high myopathy risk."
    },
    "aspirin": {
        "standard_max_mg_per_day": 4000,
        "notes": "High GI bleeding risk."
    }
}
