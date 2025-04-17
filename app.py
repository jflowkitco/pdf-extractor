import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        return full_text

def extract_fields_from_text(text):
    prompt = f"""
You are an expert in analyzing insurance quote documents. Your job is to extract clearly labeled fields and summarize relevant sections, even if the formatting is inconsistent.

Extract the following information. Use inference where needed. If information is not available, return "Not specified":

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
- Coverage Type (e.g. Property, Liability, Umbrella)
- Carrier Name
- Broker Name
- Underwriting Contact Email

Also infer the following deductible fields if present anywhere in the document:

- Wind Deductible
- Hail Deductible
- Named Storm Deductible
- All Other Perils Deductible
- Deductible Notes (if there are multiple deductible types or limitations)

And finally, provide summaries for:

- Endorsements Summary (include endorsement names or form numbers)
- Exclusions Summary (list key exclusions such as flood, terrorism, etc.)

Return the result in this format exactly:

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
    fields = [
        "Insured Name", "Named Insured Type", "Mailing Address", "Property Address",
        "Effective Date", "Expiration Date", "Premium", "Taxes", "Fees",
        "Total Insured Value", "Policy Number", "Coverage Type", "Carrier Name",
        "Broker Name", "Underwriting Contact Email",
        "Wind Deductible", "Hail Deductible", "Named Storm Deductible",
        "All Other Perils Deductible", "Deductible Notes",
        "Endorsements Summary", "Exclusions Summary"
    ]

    data = {field: "Not specified" for field in fields}
    lines = text_output.strip().splitlines()
    current_field = None

    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in data:
                current_field = key
                data[key] = value
        elif current_field:
            data[current_field] += "\n" + line.strip()

    return data

# Streamlit UI
st.set_page_config(page_title="Insurance PDF Extractor", layout="wide")

st.markdown("""
    <style>
        h1 { color: #3A699A; }
        .stButton>button { background-color: #218784; color: white; border-radius: 10px; padding: 0.5em 1em; }
        .stDownloadButton>button { background-color: #BF7F2B; color: white; border-radius: 10px; padding: 0.5em 1em; }
    </style>
    <img src="https://raw.githubusercontent.com/jflowkitco/pdf-extractor/main/KITCO%20HORIZ%20FULL%20(1).png" width="300">
    <h1>Insurance Document Extractor</h1>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    st.info("Extracting all pages from PDF...")
    text = extract_text_from_pdf(uploaded_file)

    st.success("Sending to GPT for structured extraction...")
    fields_output = extract_fields_from_text(text)
    data_dict = parse_output_to_dict(fields_output)

    st.subheader("📝 Extracted Summary")
    for key, value in data_dict.items():
        if key not in ["Endorsements Summary", "Exclusions Summary"]:
            st.markdown(f"**{key}:** {value}")

    st.markdown("---")
    st.markdown(f"### Endorsements Summary\n{data_dict['Endorsements Summary']}")
    st.markdown(f"### Exclusions Summary\n{data_dict['Exclusions Summary']}")

    csv = pd.DataFrame([data_dict]).to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", data=csv, file_name="extracted_data.csv", mime="text/csv")
