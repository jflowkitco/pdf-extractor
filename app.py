import streamlit as st
import pdfplumber
import pandas as pd
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

# Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_fields_from_text(text):
    prompt = f"""
You are an insurance document extraction assistant.

Extract the following fields from the insurance text. Look for synonyms and phrases like "premium: $5,000 (plus taxes)" or "Fees – $50". Capture values even if part of a sentence or parentheses.

### Fields:
- Insured Name
- Named Insured Type
- Mailing Address
- Property Address
- Effective Date
- Expiration Date
- Premium
- Taxes
- Fees
- Total Insured Value
- Policy Number
- Coverage Type (Property, Liability, Umbrella, etc.)
- Carrier Name
- Broker Name
- Underwriting Contact Email

### Deductibles (use judgment if not labeled exactly):
- Wind Deductible
- Hail Deductible
- Named Storm Deductible
- All Other Perils Deductible
- Deductible Notes (describe deductible context if available)

### Summaries:
- Endorsements Summary
- Exclusions Summary

Return values in this format:

Insured Name: ...
Named Insured Type: ...
...
Premium: ...
Taxes: ...
Fees: ...
...
Deductible Notes: ...
Endorsements Summary: ...
Exclusions Summary: ...

--- DOCUMENT START ---
{text[:6000]}
--- DOCUMENT END ---
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content

def fallback_regex(text, field_name):
    if field_name == "Premium":
        match = re.search(r"Premium[^$\n]*\$[0-9,]+(?:\.\d{2})?", text, re.IGNORECASE)
    elif field_name == "Taxes":
        match = re.search(r"Tax(?:es)?[^$\n]*\$[0-9,]+(?:\.\d{2})?", text, re.IGNORECASE)
    elif field_name == "Fees":
        match = re.search(r"Fee(?:s)?[^$\n]*\$[0-9,]+(?:\.\d{2})?", text, re.IGNORECASE)
    elif field_name == "Policy Number":
        match = re.search(r"(Policy\s?(Number|No\.?)[:\s]*)([\w\-\/]+)", text, re.IGNORECASE)
        return match.group(3).strip() if match else "N/A"
    else:
        return "N/A"
    return match.group(0).split("$")[1].strip() if match else "N/A"

def parse_output_to_dict(text_output, original_text):
    expected_fields = [
        "Insured Name", "Named Insured Type", "Mailing Address", "Property Address",
        "Effective Date", "Expiration Date", "Premium", "Taxes", "Fees",
        "Total Insured Value", "Policy Number", "Coverage Type", "Carrier Name",
        "Broker Name", "Underwriting Contact Email", "Wind Deductible", "Hail Deductible",
        "Named Storm Deductible", "All Other Perils Deductible", "Deductible Notes",
        "Endorsements Summary", "Exclusions Summary"
    ]

    data = {field: "N/A" for field in expected_fields}
    lines = text_output.strip().splitlines()
    current_field = None
    for line in lines:
        if ":" in line:
            key_part, value_part = line.split(":", 1)
            key = key_part.strip()
            value = value_part.strip()
            if key in expected_fields:
                current_field = key
                data[current_field] = value
        elif current_field:
            data[current_field] += " " + line.strip()

    # Fallback if GPT missed these
    for fallback_field in ["Premium", "Taxes", "Fees", "Policy Number"]:
        if data[fallback_field] == "N/A":
            data[fallback_field] = fallback_regex(original_text, fallback_field)

    return data

# Streamlit UI
st.set_page_config(page_title="Insurance PDF Extractor", layout="wide")
st.markdown("""
    <style>
        .reportview-container .main { background-color: #F9FAFB; padding: 2rem; }
        h1 { color: #3A699A; }
        .stButton>button { background-color: #218784; color: white; border-radius: 10px; padding: 0.5em 1em; }
        .stDownloadButton>button { background-color: #BF7F2B; color: white; border-radius: 10px; padding: 0.5em 1em; }
    </style>
    <img src="https://raw.githubusercontent.com/jflowkitco/pdf-extractor/main/KITCO%20HORIZ%20FULL%20(1).png" width="300">
    <h1>Insurance Document Extractor</h1>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    st.info("Extracting text from PDF...")
    raw_text = extract_text_from_pdf(uploaded_file)

    st.success("Sending to GPT...")
    extracted = extract_fields_from_text(raw_text)
    data_dict = parse_output_to_dict(extracted, raw_text)

    st.subheader("📝 Summary")
    for key, value in data_dict.items():
        if key not in ["Endorsements Summary", "Exclusions Summary"]:
            st.markdown(f"**{key}:** {value}")

    st.markdown("---")
    st.markdown(f"""
    **Endorsements Summary**  
    {data_dict['Endorsements Summary']}  

    **Exclusions Summary**  
    {data_dict['Exclusions Summary']}
    """)

    csv = pd.DataFrame([data_dict]).to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="extracted_data.csv",
        mime="text/csv"
    )
