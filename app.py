import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load API key from .env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def extract_fields_from_text(text):
    prompt = f"""
You are an expert insurance document parser. Extract the following fields using contextual understanding. 
The information may appear anywhere in the document and may be phrased differently. Match and infer best-fit values.

**Fields to extract:**
- Insured Name
- Named Insured Type (LLC, Trust, Individual)
- Mailing Address
- Property Address
- Effective Date
- Expiration Date
- Premium (total premium amount)
- Taxes (any applicable premium tax or breakdown)
- Fees (any policy fees)
- Total Insured Value
- Policy Number
- Coverage Type (Property, Liability, Umbrella, etc.)
- Carrier Name
- Broker Name
- Underwriting Contact Email

**Deductibles to infer:**
- Wind Deductible
- Hail Deductible
- Named Storm Deductible
- All Other Perils Deductible
- Deductible Notes (explain any related language)

**Summaries:**
- Endorsements Summary
- Exclusions Summary

Return values exactly in this format:

Insured Name: ...
Named Insured Type: ...
Mailing Address: ...
Property Address: ...
Effective Date: ...
Expiration Date: ...
Premium: ...
Taxes: ...
Fees: ...
Total Insured Value: ...
Policy Number: ...
Coverage Type: ...
Carrier Name: ...
Broker Name: ...
Underwriting Contact Email: ...
Wind Deductible: ...
Hail Deductible: ...
Named Storm Deductible: ...
All Other Perils Deductible: ...
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

def parse_output_to_dict(text_output):
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
            data[current_field] += "\n" + line.strip()
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
    text = extract_text_from_pdf(uploaded_file)

    st.success("Sending to GPT...")
    fields_output = extract_fields_from_text(text)
    data_dict = parse_output_to_dict(fields_output)

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
