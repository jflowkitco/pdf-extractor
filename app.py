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
Extract the following details from this insurance document, making your best inference based on context:

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

Now infer the deductible amounts or percentages for the following, even if not explicitly labeled:

- Wind Deductible
- Hail Deductible
- Named Storm Deductible
- All Other Perils Deductible

Use the following logic:
- Look for words like “wind,” “hail,” “named storm,” “AOP,” “all other perils,” or “all other causes of loss.”
- Deductibles may be listed as flat dollar amounts, percentages, or percentages with minimums (e.g. “2% subject to a $100,000 minimum”).
- If a deductible is listed in a general section, try to assign it to the most relevant peril type.
- If only one deductible is listed, assume it applies to “All Other Perils.”
- If deductible info is unclear or not present, return "N/A".

Return the results in this format exactly:

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
        "All Other Perils Deductible"
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
st.set_page_config(page_title="Insurance PDF Extractor")
st.title("📄 Insurance Document Extractor")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    st.info("Extracting text from PDF...")
    text = extract_text_from_pdf(uploaded_file)

    st.success("Sending to GPT...")
    fields_output = extract_fields_from_text(text)
    st.code(fields_output)

    data_dict = parse_output_to_dict(fields_output)
    df = pd.DataFrame([data_dict])

    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="extracted_data.csv",
        mime="text/csv"
    )
