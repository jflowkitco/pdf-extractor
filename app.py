import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
import openai
from fpdf import FPDF
import tempfile
from PyPDF2 import PdfMerger

# Load API key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

KITCO_BLUE = (33, 135, 132)
KITCO_GREEN = (61, 153, 93)
KITCO_LOGO_PATH = "KITCO_HORIZ_FULL.png"  # Ensure this file is uploaded with the app

# PDF Text Extraction
def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        return "\n".join([page.extract_text() or "" for page in pdf.pages])

# GPT Prompt & Response
def extract_fields_from_text(text):
    prompt = f"""
Extract the following details from this insurance document:

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
- Wind Deductible
- Hail Deductible
- Named Storm Deductible
- All Other Perils Deductible
- Deductible Notes
- Endorsements Summary (bullet list format)
- Exclusions Summary (bullet list format)

Return results in this format exactly:

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
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content

# Parsing Output + Calculated Rate
def parse_output_to_dict(text_output):
    data = {}
    for line in text_output.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()

    try:
        premium = float(data.get("Premium", "").replace("$", "").replace(",", ""))
        tiv = float(data.get("Total Insured Value", "").replace("$", "").replace(",", ""))
        data["Rate"] = f"${(premium / tiv * 100):.3f}" if tiv > 0 else "N/A"
    except:
        data["Rate"] = "N/A"

    return data

# PDF Summary Generator
class SummaryPDF(FPDF):
    def header(self):
        if os.path.exists(KITCO_LOGO_PATH):
            self.image(KITCO_LOGO_PATH, 10, 8, 60)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*KITCO_BLUE)
        self.ln(20)
        self.cell(0, 10, "Insurance Summary", ln=True, align="C")
        self.ln(10)

    def add_data_section(self, title, fields, data):
        self.set_text_color(*KITCO_GREEN)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 8, title, ln=True)
        self.set_font("Helvetica", size=11)

        for field in fields:
            value = data.get(field, "N/A")
            self.set_text_color(*KITCO_BLUE)
            label = f"{field}: "
            self.cell(self.get_string_width(label), 6, label, ln=False)
            self.set_text_color(0, 0, 0)
            self.cell(0, 6, value, ln=True)

        self.ln(2)

    def add_bullet_section(self, title, content):
        self.set_text_color(*KITCO_GREEN)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 8, title, ln=True)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(0, 0, 0)

        for item in content.split(" - "):
            if item.strip():
                self.cell(5)
                self.multi_cell(0, 5, f"• {item.strip()}", align="L")
        self.ln(2)

def generate_pdf_summary(data, filename):
    pdf = SummaryPDF()
    pdf.add_page()
    pdf.add_data_section("Insured Details", [
        "Insured Name", "Named Insured Type", "Mailing Address", "Property Address",
        "Underwriting Contact Email"
    ], data)
    pdf.add_data_section("Coverage Dates and Values", [
        "Effective Date", "Expiration Date", "Premium", "Taxes", "Fees", "Total Insured Value", "Rate"
    ], data)
    pdf.add_data_section("Policy Info", [
        "Policy Number", "Coverage Type", "Carrier Name", "Broker Name"
    ], data)
    pdf.add_data_section("Deductibles", [
        "Wind Deductible", "Hail Deductible", "Named Storm Deductible",
        "All Other Perils Deductible", "Deductible Notes"
    ], data)
    pdf.add_bullet_section("Endorsements Summary", data.get("Endorsements Summary", "N/A"))
    pdf.add_bullet_section("Exclusions Summary", data.get("Exclusions Summary", "N/A"))
    pdf.output(filename)

def merge_pdfs(summary_path, original_path, output_path):
    merger = PdfMerger()
    merger.append(summary_path)
    try:
        merger.append(original_path)
    except:
        pass
    merger.write(output_path)
    merger.close()

# Streamlit App
st.set_page_config(page_title="Insurance PDF Extractor")
st.title("📄 Insurance Document Extractor")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    st.info("Extracting text from PDF...")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_uploaded:
        temp_uploaded.write(uploaded_file.read())
        temp_uploaded_path = temp_uploaded.name

    text = extract_text_from_pdf(temp_uploaded_path)
    st.success("Sending to GPT...")
    fields_output = extract_fields_from_text(text)
    st.code(fields_output)

    data_dict = parse_output_to_dict(fields_output)
    st.dataframe(pd.DataFrame([data_dict]))

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_summary:
        generate_pdf_summary(data_dict, temp_summary.name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_merged:
            merge_pdfs(temp_summary.name, temp_uploaded_path, temp_merged.name)
            with open(temp_merged.name, "rb") as f:
                st.download_button(
                    label="📥 Download Merged PDF Report",
                    data=f.read(),
                    file_name="insurance_summary.pdf",
                    mime="application/pdf"
                )
