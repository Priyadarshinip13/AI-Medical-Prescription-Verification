# frontend/streamlit_app.py
import streamlit as st
import requests
import pandas as pd
import json

API_BASE = st.secrets.get("api_base", "http://localhost:8000")

st.set_page_config(page_title="AI Medical Prescription Verification", layout="wide")
st.title("AI Medical Prescription Verification — Clinician Dashboard")

# Sidebar patient info + history lookup
with st.sidebar:
    st.header("Patient Info")
    patient_name = st.text_input("Patient name (for history)", value="")
    age = st.number_input("Age (years)", 0.0, 120.0, 45.0)
    weight = st.number_input("Weight (kg)", 0.0, 300.0, 60.0)
    egfr = st.number_input("eGFR", 0.0, 200.0, 90.0)
    allergies = st.text_input("Allergies (comma separated)")

    st.markdown("---")
    st.subheader("History")
    history_query = st.text_input("Search patient history (name)", value=patient_name)
    if st.button("Load History"):
        if not history_query.strip():
            st.warning("Enter a patient name to search history.")
        else:
            try:
                r = requests.get(f"{API_BASE}/history/{history_query}")
                if r.status_code == 200:
                    hist = r.json()
                    if hist:
                        st.success(f"Found {len(hist)} records for '{history_query}'. Scroll in main UI.")
                        st.session_state["history_loaded"] = hist
                    else:
                        st.info("No history found.")
                        st.session_state["history_loaded"] = []
                else:
                    st.error("History lookup failed: " + r.text)
            except Exception as e:
                st.error("Could not contact backend: " + str(e))

# Main layout: left input / right results
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("Input Prescription")
    uploaded = st.file_uploader("Upload prescription image (png/jpg/pdf)", type=["png","jpg","jpeg","pdf"])
    plain_text = st.text_area("Or paste prescription text here (optional)", height=120)

    if st.button("Run OCR & Extract"):
        st.info("Calling /extract...")
        try:
            if uploaded:
                files = {"file": ("prescription", uploaded.getvalue(), uploaded.type)}
                resp = requests.post(f"{API_BASE}/extract", files=files, timeout=60)
            else:
                resp = requests.post(f"{API_BASE}/extract", data={"text": plain_text}, timeout=30)
            if resp.status_code != 200:
                st.error("Extraction failed: " + resp.text)
            else:
                ex = resp.json()
                st.session_state["ocr_text"] = ex.get("raw_text", "") or ex.get("ocr_text", "") or plain_text
                meds = ex.get("meds", []) or ex.get("meds_raw", []) or []
                # convert meds to DataFrame for editing
                if meds:
                    df = pd.DataFrame([m if isinstance(m, dict) else m.__dict__ for m in meds])
                else:
                    df = pd.DataFrame(columns=["drug","strength","unit","frequency_per_day","route"])
                st.session_state["meds_df"] = df
                st.success("Extraction complete. Edit meds if necessary and click Verify.")
        except Exception as e:
            st.error("Error calling /extract: " + str(e))

    st.markdown("---")
    st.subheader("Parsed Medications (editable)")
    meds_df = st.session_state.get("meds_df", pd.DataFrame(columns=["drug","strength","unit","frequency_per_day","route"]))
    edited_df = st.data_editor(meds_df, num_rows="dynamic", key="meds_editor")

    if st.button("Verify & Save to History"):
        meds_list = edited_df.to_dict(orient="records")
        payload = {
            "patient": {
                "name": patient_name or "Unknown",
                "age_years": float(age),
                "weight_kg": float(weight),
                "egfr": float(egfr),
                "allergies": [a.strip() for a in allergies.split(",") if a.strip()]
            },
            "meds": meds_list
        }
        st.json(payload)
        try:
            r = requests.post(f"{API_BASE}/analyze", json=payload, timeout=60)
            if r.status_code != 200:
                st.error("Analysis failed: " + r.text)
            else:
                out = r.json()
                st.session_state["last_analysis"] = {"payload": payload, "result": out}
                st.success("Analysis complete and saved to history.")
                # display results immediately in right column by setting state
                st.rerun()

        except Exception as e:
            st.error("Failed to call /analyze: " + str(e))

with col2:
    st.subheader("OCR Output (raw text)")
    ocr_text = st.session_state.get("ocr_text", "")
    if ocr_text:
        st.text_area("OCR Text", value=ocr_text, height=180)
    else:
        st.write("No OCR text available. Run extraction first or paste text.")

    st.subheader("Latest Analysis Results")
    last = st.session_state.get("last_analysis")
    if last:
        out = last["result"]
        st.markdown("**Dose Issues**")
        if out.get("dose_issues"):
            for d in out.get("dose_issues"):
                if isinstance(d, dict):
                    st.markdown(f"- **{d.get('drug','')}**: {d.get('message')}")
                else:
                    st.markdown(f"- {d}")
        else:
            st.success("✅ No dose issues detected.")

        st.markdown("**Interactions**")
        if out.get("interactions"):
            for it in out.get("interactions"):
                st.markdown(f"- {it}")
        else:
            st.success("✅ No interactions detected.")

        st.markdown("**Suggested Alternatives**")
        if out.get("alternatives"):
            for alt in out.get("alternatives"):
                st.markdown(f"- {alt}")
        else:
            st.info("ℹ️ No alternatives suggested.")
    else:
        st.info("No recent analysis. Run Verify & Save to store results.")

    st.markdown("---")
    st.subheader("Patient History (loaded)")
    history = st.session_state.get("history_loaded", [])
    if history:
        for rec in history:
            st.markdown(f"**Date:** {rec.get('date')}  —  **Patient:** {rec.get('patient_name')}")
            st.markdown("- **Medications**")
            st.json(rec.get("meds"))
            st.markdown("- **Dose Issues**")
            st.write(rec.get("dose_issues") or "None")
            st.markdown("- **Interactions**")
            st.write(rec.get("interactions") or "None")
            st.markdown("- **Alternatives**")
            st.write(rec.get("alternatives") or "None")
            st.markdown("---")
    else:
        st.write("No history loaded. Use the sidebar to search a patient's history.")


