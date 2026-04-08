import streamlit as st
import tempfile
import json
import os

from pdf_reader import extract_text
from preprocessor import preprocess
from extractor import extract_entities

st.set_page_config(page_title="Insurance Doc Parser", layout="wide")
st.title("Insurance Document Parser")
st.caption("Extract policy numbers, dates, amounts, and parties from insurance PDFs")

uploaded = st.file_uploader("Upload an insurance PDF", type="pdf")

if uploaded:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    try:
        with st.spinner("Reading PDF..."):
            pages = extract_text(tmp_path)

        if not pages:
            st.error("No text found. The document may be image-only and require OCR.")
            st.stop()

        with st.spinner("Preprocessing text..."):
            text = preprocess(pages)

        with st.spinner("Running entity extraction..."):
            entities = extract_entities(text)

        st.success(f"Parsed {len(pages)} page(s) — {len(text):,} characters")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Extracted Entities")

            section_labels = {
                "policy_numbers": "Policy Numbers",
                "dates": "Dates",
                "amounts": "Amounts",
                "parties": "Parties",
            }

            for key, label in section_labels.items():
                items = entities[key]
                with st.expander(f"{label} ({len(items)} found)", expanded=True):
                    if not items:
                        st.caption("None found")
                    else:
                        for item in items:
                            conf = item["confidence"]
                            type_tag = f" · {item['type']}" if "type" in item else ""
                            color = "green" if conf >= 0.90 else "orange" if conf >= 0.80 else "red"
                            st.markdown(
                                f"`{item['value']}`{type_tag} "
                                f"<span style='color:{color}'>▮ {conf:.0%}</span>",
                                unsafe_allow_html=True,
                            )

        with col2:
            st.subheader("JSON Output")
            st.json(entities)
            st.download_button(
                "Download JSON",
                data=json.dumps(entities, indent=2),
                file_name="extracted_entities.json",
                mime="application/json",
            )

        with st.expander("Extracted text (first 3,000 characters)"):
            st.text(text[:3000] + ("..." if len(text) > 3000 else ""))

    finally:
        os.unlink(tmp_path)
