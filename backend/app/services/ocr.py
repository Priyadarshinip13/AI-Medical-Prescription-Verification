# backend/app/services/ocr.py
import io
import logging
from PIL import Image

log = logging.getLogger("ocr")

# Load IBM Granite Vision OCR
from transformers import pipeline
import torch

try:
    device = 0 if torch.cuda.is_available() else -1
    granite_pipe = pipeline(
        "image-to-text",
        model="ibm-granite/granite-vision-3.2-2b",
        device=device
    )
    log.info("✅ Granite Vision loaded successfully")
except Exception as e:
    granite_pipe = None
    log.error(f"❌ Failed to load Granite Vision: {e}")

# IBM Watson NLP
import requests
import os

WATSON_API_KEY = os.getenv("WATSON_API_KEY")  # Set in .env or environment variables
WATSON_URL = os.getenv("WATSON_URL")  # Your Watson NLP endpoint URL


def image_to_entities(image_bytes: bytes):
    """
    Convert prescription image to structured medication data.
    Steps:
    1) OCR using Granite Vision
    2) Send text to Watson NLP for drug extraction
    """
    if not granite_pipe:
        raise RuntimeError("Granite Vision model not loaded")

    # Step 1: OCR with Granite
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    granite_out = granite_pipe(img)
    ocr_text = "\n".join([x.get("generated_text", "") for x in granite_out if x.get("generated_text")])

    if not ocr_text.strip():
        log.warning("OCR returned empty text")
        return {"text": "", "entities": []}

    # Step 2: Watson NLP for Drug Extraction
    try:
        payload = {
            "text": ocr_text,
            "features": {
                "entities": {
                    "model": "drug",  # Watson Health NLP model for medications
                    "mentions": True
                }
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {WATSON_API_KEY}"
        }
        watson_response = requests.post(WATSON_URL, json=payload, headers=headers, timeout=20)
        watson_data = watson_response.json()

        # Extract structured drug data
        meds = []
        for ent in watson_data.get("entities", []):
            if ent.get("type") == "Drug":
                meds.append({
                    "name": ent.get("text"),
                    "dose_mg": ent.get("attributes", {}).get("strength"),
                    "frequency_per_day": ent.get("attributes", {}).get("frequency"),
                    "route": ent.get("attributes", {}).get("route")
                })

        return {"text": ocr_text, "entities": meds}

    except Exception as e:
        log.error(f"Watson NLP extraction failed: {e}")
        return {"text": ocr_text, "entities": []}
