import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI
from fpdf import FPDF
import tempfile
from PyPDF2 import PdfMerger, PdfReader

# Load API key from .env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

KITCO_BLUE = (33, 135, 132)
KITCO_GREEN = (61, 153, 93)
KITCO_GOLD = (191, 127, 43)

KITCO_LOGO_PATH = "KITCO_HORIZ_FULL.png"  # Ensure this is uploaded with your app

def extract_text_by_page(pdf_file):
    page_texts = []
    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                page_texts.append((i + 1, text))
    return page_texts

def extract_fields_from_text(text):
    prompt = f"""
You are an insurance policy analysis bot.

Your job is to extract and infer the following fields from the insurance document below. Use context and examples to identify data even when labels are inconsistent. Look for information in sections like premium breakdowns, declarations, or coverage summaries.

**Fields to extract:**
- Insured Name
- Named Insured Type (e.g. LLC, Trust, Individual)
- Mailing Address
- Property Address
- Effective Date
- Expiration Date
- Premium (total or combined if multiple lines)
- Taxes
- Fees
- Total Insured Value
- Policy Number (look near the top, in declaration or coverage summary pages)
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

Return the data in this exact format:
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
{text}
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
            data[current_field] += " " + line.strip()

    # Add rate calculation if Premium and Total Insured Value are present
    try:
        premium = float(data["Premium"].replace("$", "").replace(",", ""))
        tiv = float(data["Total Insured Value"].replace("$", "").replace(",", ""))
        if tiv > 0:
            rate = (premium / tiv) * 100
            data["Rate"] = f"${rate:.3f}"
        else:
            data["Rate"] = "N/A"
    except:
        data["Rate"] = "N/A"

    return data

# Other functions remain unchanged...
