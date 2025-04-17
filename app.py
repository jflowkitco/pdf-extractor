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
            text += page.extract_text() + "\n"
    return text

def extract_fields_from_text(text):
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
- Coverage Type (e.g. Special, Basic, Fire Only)
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

Look for section titles or phrases like:
- "Forms and Endorsements"
- "This policy excludes…"
- "The following is added to…"

If any fields are not present, return "N/A".

**Return the data in this exact format:**
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
        "Insured Name",
        "Named Insured Type",
        "Mailing Address",
        "Property Address",
        "Effective Date",
        "Expiration Date",
        "Premium",
        "Taxes",
        "Fees",
        "Total Insured Value",
        "Policy Number",
        "Coverage Type",
        "Carrier Name",
        "Broker Name",
        "Underwriting Contact Email",
        "Wind Deductible",
        "Hail Deductible",
        "Named Storm Deductible",
        "All Other Perils Deductible",
        "Deductible Notes",
        "Endorsements Summary",
        "Exclusions Summary"
    ]

    data = {field: "N/A" for field in expected_fields}

    for line in text_output.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in data:
                data[key] = value if value else "N/A"

    return data

# Streamlit UI
st.set_page_config(page_title="Insurance PDF Extractor", layout="wide")
st.title("\U0001F4C4 Insurance Document Extractor")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    st.info("Extracting text from PDF...")
    text = extract_text_from_pdf(uploaded_file)

    st.success("Sending to GPT...")
    fields_output = extract_fields_from_text(text)
    data_dict = parse_output_to_dict(fields_output)

    st.subheader("\U0001F4DD Summary")
    st.markdown(f"""
    **Insured Name:** {data_dict['Insured Name']}  
    **Named Insured Type:** {data_dict['Named Insured Type']}  
    **Mailing Address:** {data_dict['Mailing Address']}  
    **Property Address:** {data_dict['Property Address']}  
    **Effective Date:** {data_dict['Effective Date']}  
    **Expiration Date:** {data_dict['Expiration Date']}  
    **Premium:** {data_dict['Premium']}  
    **Taxes:** {data_dict['Taxes']}  
    **Fees:** {data_dict['Fees']}  
    **Total Insured Value:** {data_dict['Total Insured Value']}  
    **Policy Number:** {data_dict['Policy Number']}  
    **Coverage Type:** {data_dict['Coverage Type']}  
    **Carrier Name:** {data_dict['Carrier Name']}  
    **Broker Name:** {data_dict['Broker Name']}  
    **Underwriting Contact Email:** {data_dict['Underwriting Contact Email']}  
    
    **Wind Deductible:** {data_dict['Wind Deductible']}  
    **Hail Deductible:** {data_dict['Hail Deductible']}  
    **Named Storm Deductible:** {data_dict['Named Storm Deductible']}  
    **All Other Perils Deductible:** {data_dict['All Other Perils Deductible']}  
    **Deductible Notes:** {data_dict['Deductible Notes']}  

    ---
    **Endorsements Summary**  
    {data_dict['Endorsements Summary']}

    **Exclusions Summary**  
    {data_dict['Exclusions Summary']}
    """)

    csv = pd.DataFrame([data_dict]).to_csv(index=False).encode("utf-8")
    st.download_button(
        label="\U0001F4E5 Download CSV",
        data=csv,
        file_name="extracted_data.csv",
        mime="text/csv"
    )