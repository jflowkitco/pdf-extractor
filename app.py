import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI
import re

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

def chunk_text(text, max_chars=6000):
    chunks = []
    while len(text) > max_chars:
        split_index = text[:max_chars].rfind("\n")
        if split_index == -1:
            split_index = max_chars
        chunks.append(text[:split_index])
        text = text[split_index:]
    chunks.append(text)
    return chunks

def extract_fields_from_text(text):
    chunks = chunk_text(text)
    combined_response = ""

    for i, chunk in enumerate(chunks):
        prompt = f"""
You are an insurance policy analysis bot.

Your job is to extract and infer the following fields from the insurance document below. Use context and examples to identify data even when labels are inconsistent.

**Fields to extract:**
- Insured Name
- Named Insured Type (e.g. LLC, Trust, Individual)
- Mailing Address
- Property Address
- Effective Date
- Expiration Date
- Premium
- Taxes
- Fees
- Total Insured Value
- Policy Number
- Coverage Type (e.g. Property, Liability, Umbrella)
- Carrier Name
- Broker Name
- Underwriting Contact Email

**Deductibles to infer (even if not explicitly labeled):**
- Wind Deductible
- Hail Deductible
- Named Storm Deductible
- All Other Perils Deductible
- Deductible Notes (brief summary of any deductible-related language or assumptions)

**Endorsement & Exclusion Summary:**
Separate into two fields:
- Endorsements Summary
- Exclusions Summary

If any fields are not present, return "N/A". For the summaries, return "N/A" if no content is found.

Return the data in this exact format with readable wrapping and line breaks for summaries:
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
{chunk}
--- DOCUMENT END ---
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        combined_response += response.choices[0].message.content + "\n"

    return combined_response

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
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 15px; border: 1px solid #ddd; text-align: left; }
        th { background-color: #3A699A; color: white; }
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

    st.subheader("📝 Extracted Details")

    # Create a DataFrame for clean tabular display
    table_df = pd.DataFrame(list(data_dict.items()), columns=["Field", "Value"])
    st.markdown("""
    <table>
        <thead><tr><th>Field</th><th>Value</th></tr></thead>
        <tbody>
    """, unsafe_allow_html=True)
    for _, row in table_df.iterrows():
        st.markdown(f"<tr><td>{row['Field']}</td><td>{row['Value'].replace(chr(10), '<br>')}</td></tr>", unsafe_allow_html=True)
    st.markdown("""
        </tbody>
    </table>
    """, unsafe_allow_html=True)

    # Downloadable CSV
    csv = pd.DataFrame([data_dict]).to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="extracted_data.csv",
        mime="text/csv"
    )