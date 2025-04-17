import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load .env and set API key
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
