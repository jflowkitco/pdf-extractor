import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
import openai
from openai import OpenAI
from fpdf import FPDF
import tempfile
from PyPDF2 import PdfMerger
import re
import json

# Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

KITCO_BLUE = (33, 135, 132)
KITCO_GREEN = (61, 153, 93)
KITCO_GOLD = (191, 127, 43)
KITCO_LOGO_PATH = "KITCO_HORIZ_FULL.png"

# Extract all text from PDF
def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

# Extract page 5 for accurate premium/tax/fee/policy number info
def extract_page_five_text(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        if len(pdf.pages) >= 5:
            return pdf.pages[4].extract_text()
        return ""

# Extract TIV from all pages
def extract_tiv_from_all_pages(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text

# Ask GPT to extract details
def extract_fields_from_text(text, page_five_text, tiv_text):
    prompt = f"""
You are an insurance document analyst. Extract the following details from the document:

Focus only on page 5 for:
- Premium (look for line item labeled Premium: $... or Total Premium)
- Fees (look for Policy Fee or similar)
- Taxes (look for Surplus Lines Tax, State Tax, etc.)
- Policy Number (look for number format typically 7+ digits long)
- Ignore anything labeled TRIA premium

Focus on the entire document for:
- Add up the limits for the following components to calculate Total Insured Value (TIV):
  - Building coverage
  - Business Personal Property
  - Business Income / Rental Value
  - Other Structures
  - Any other property-related coverage with a dollar limit

Then extract:
- Insured Name
- Named Insured Type
- Mailing Address
- Property Address
- Effective Date
- Expiration Date
- Coverage Type
- Carrier Name
- Broker Name
- Underwriting Contact Email
- Wind Deductible
- Hail Deductible
- Named Storm Deductible
- All Other Perils Deductible
- Deductible Notes
- Endorsements Summary (list all endorsements, if any)
- Exclusions Summary (list all exclusions, if any)

If both Premium and TIV are present, calculate and return the rate as:
Rate: $(Premium / TIV * 100) formatted to 3 decimal places

Return the results exactly like this:
Insured Name: ...
Named Insured Type: ...
Mailing Address: ...
Property Address: ...
Effective Date: ...
Expiration Date: ...
Premium: ...
Rate: ...
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
Endorsements Summary:
- ...
Exclusions Summary:
- ...

--- PAGE 5 ---
{page_five_text}
--- TIV TEXT ---
{tiv_text}
--- DOCUMENT ---
{text[:8000]}
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content, prompt

# Convert GPT output to dictionary
def parse_output_to_dict(text_output):
    data = {}
    for line in text_output.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()

    try:
        premium = float(re.sub(r"[^\d.]", "", data.get("Premium", "0")))
        tiv = float(re.sub(r"[^\d.]", "", data.get("Total Insured Value", "0")))
        if premium > 0 and tiv > 0:
            rate = premium / tiv * 100
            data["Rate"] = f"${rate:.3f}"
        else:
            data["Rate"] = "N/A"
    except Exception:
        data["Rate"] = "N/A"

    return data

# PDF layout
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
        self.cell(0, 10, title, ln=True)
        self.set_font("Helvetica", size=11)
        for field in fields:
            value = data.get(field, "N/A")
            self.set_text_color(*KITCO_BLUE)
            self.cell(60, 6, f"{field}:", ln=False)
            self.set_text_color(0, 0, 0)
            self.multi_cell(0, 6, sanitize_text(f"{value}"), align="L")

    def add_bullet_section(self, title, content):
        self.set_text_color(*KITCO_GREEN)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, title, ln=True)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", size=8)
        for line in content.split("\n"):
            for bullet in line.split(" - "):
                if bullet.strip():
                    self.cell(5)
                    self.multi_cell(0, 5, f"• {sanitize_text(bullet.strip())}", align="L")

# Helper to clean unicode
def sanitize_text(text):
    return text.encode("latin1", "replace").decode("latin1")

# Create and save PDF
def generate_pdf_summary(data, filename):
    pdf = SummaryPDF()
    pdf.add_page()
    pdf.add_data_section("Insured Details", [
        "Insured Name", "Named Insured Type", "Mailing Address", "Property Address",
        "Underwriting Contact Email"
    ], data)
    pdf.add_data_section("Coverage Dates and Values", [
        "Effective Date", "Expiration Date", "Premium", "Rate", "Taxes", "Fees", "Total Insured Value"
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
    pdf.output(filename, "F")

# Merge summary + source PDF
def merge_pdfs(summary_path, original_path, output_path):
    merger = PdfMerger()
    merger.append(summary_path)
    try:
        merger.append(original_path)
    except Exception:
        pass
    merger.write(output_path)
    merger.close()

# Streamlit app
st.set_page_config(page_title="Insurance PDF Extractor")
st.title("📄 Insurance Document Extractor")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    st.info("Extracting text from PDF...")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_uploaded:
        temp_uploaded.write(uploaded_file.read())
        temp_uploaded_path = temp_uploaded.name

    text = extract_text_from_pdf(temp_uploaded_path)
    page_five_text = extract_page_five_text(temp_uploaded_path)
    tiv_text = extract_tiv_from_all_pages(temp_uploaded_path)
    st.success("Sending to GPT...")
    fields_output, prompt = extract_fields_from_text(text, page_five_text, tiv_text)
    st.code(fields_output)

    data_dict = parse_output_to_dict(fields_output)
    df = pd.DataFrame([data_dict])
    st.dataframe(df)

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

    if st.button("💾 Save as Training Data Example"):
        fine_tune_example = {
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": fields_output}
            ]
        }
        with open("fine_tuning_examples.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(fine_tune_example) + "\n")
        st.success("✅ Saved for fine-tuning.")
