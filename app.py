import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI
from fpdf import FPDF
import tempfile
from PyPDF2 import PdfMerger, PdfReader

# Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

KITCO_BLUE = (33, 135, 132)
KITCO_GREEN = (61, 153, 93)
KITCO_GOLD = (191, 127, 43)

KITCO_LOGO_PATH = "KITCO_HORIZ_FULL.png"


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

**Deductibles to infer:**
- Wind Deductible
- Hail Deductible
- Named Storm Deductible
- All Other Perils Deductible
- Deductible Notes

**Endorsement & Exclusion Summary:**
- Endorsements Summary
- Exclusions Summary

If any fields are not present, return "N/A".

Return format:
Insured Name: ...
Named Insured Type: ...
Mailing Address: ...
...
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
            data[current_field] += "\n" + line.strip()
    return data


def generate_pdf_summary(data, summary_path):
    def safe_text(text):
        return text.encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()

    if os.path.exists(KITCO_LOGO_PATH):
        pdf.image(KITCO_LOGO_PATH, x=10, y=8, w=50)
        pdf.set_y(30)

    pdf.set_font("Times", "B", 16)
    pdf.set_text_color(*KITCO_BLUE)
    pdf.cell(200, 10, txt=safe_text("Insurance Document Summary"), ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Times", size=12)
    pdf.set_text_color(0, 0, 0)
    for key, value in data.items():
        pdf.set_font("Times", "B", 12)
        pdf.set_text_color(*KITCO_GREEN)
        pdf.multi_cell(0, 8, txt=safe_text(f"{key}"), align="L")
        pdf.set_font("Times", size=12)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 8, txt=safe_text(value), align="L")
        pdf.ln(1)

    pdf.output(summary_path)


def merge_pdfs(summary_path, original_path, output_path):
    try:
        PdfReader(original_path)  # Validate file
        merger = PdfMerger()
        merger.append(summary_path)
        merger.append(original_path)
        merger.write(output_path)
        merger.close()
    except Exception as e:
        print(f"Error merging PDFs: {e}")
        # Fall back to summary only
        os.rename(summary_path, output_path)


# Streamlit UI
st.set_page_config(page_title="Insurance PDF Extractor")
st.title("📄 Insurance Document Extractor")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    st.info("Extracting text from PDF...")
    text = extract_text_from_pdf(uploaded_file)

    st.success("Sending to GPT...")
    fields_output = extract_fields_from_text(text)
    data_dict = parse_output_to_dict(fields_output)

    st.subheader("📝 Extracted Details")
    for field, value in data_dict.items():
        st.markdown(f"**{field}:** {value}")

    csv = pd.DataFrame([data_dict]).to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="extracted_data.csv",
        mime="text/csv"
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_summary, \
         tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_merged, \
         tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_uploaded:

        generate_pdf_summary(data_dict, temp_summary.name)
        temp_uploaded.write(uploaded_file.getbuffer())
        temp_uploaded_path = temp_uploaded.name

        merge_pdfs(temp_summary.name, temp_uploaded_path, temp_merged.name)

        with open(temp_merged.name, "rb") as f:
            st.download_button(
                label="📄 Download Full PDF (Summary + Original)",
                data=f.read(),
                file_name="full_summary_and_original.pdf",
                mime="application/pdf"
            )
