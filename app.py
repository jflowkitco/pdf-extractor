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
            data["Rate"] = f"{(premium / tiv) * 100:.4f}%"
        else:
            data["Rate"] = "N/A"
    except:
        data["Rate"] = "N/A"

    return data

def generate_pdf_summary(data, summary_path):
    def safe_text(text):
        return text.encode("latin-1", "replace").decode("latin-1")

    section_headers = {
        "Policy Info": ["Insured Name", "Named Insured Type", "Mailing Address", "Property Address"],
        "Coverage Dates & Values": ["Effective Date", "Expiration Date", "Premium", "Taxes", "Fees", "Total Insured Value", "Rate"],
        "Policy Details": ["Policy Number", "Coverage Type", "Carrier Name", "Broker Name", "Underwriting Contact Email"],
        "Deductibles": ["Wind Deductible", "Hail Deductible", "Named Storm Deductible", "All Other Perils Deductible", "Deductible Notes"],
        "Endorsements & Exclusions": ["Endorsements Summary", "Exclusions Summary"]
    }

    pdf = FPDF()
    pdf.add_page()

    if os.path.exists(KITCO_LOGO_PATH):
        pdf.image(KITCO_LOGO_PATH, x=10, y=8, w=50)
        pdf.set_y(30)

    pdf.set_font("Times", "B", 16)
    pdf.set_text_color(*KITCO_BLUE)
    pdf.cell(200, 10, txt=safe_text("Insurance Document Summary"), ln=True, align="C")
    pdf.ln(8)

    for section, keys in section_headers.items():
        pdf.set_font("Times", "B", 14)
        pdf.set_text_color(*KITCO_GOLD)
        pdf.cell(0, 10, txt=safe_text(section), ln=True)
        pdf.set_draw_color(180, 180, 180)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

        for key in keys:
            value = data.get(key, "N/A")
            pdf.set_font("Times", size=12)
            pdf.set_text_color(0, 0, 0)
            pdf.multi_cell(0, 8, txt=safe_text(f"{key}: {value}"), align="L")
            pdf.ln(1)
        pdf.ln(2)

    pdf.output(summary_path)

def merge_pdfs(summary_path, original_path, output_path):
    try:
        merger = PdfMerger()
        merger.append(summary_path)
        merger.append(original_path)
        merger.write(output_path)
        merger.close()
    except Exception as e:
        print("PDF merge failed:", e)

# Streamlit UI
st.set_page_config(page_title="Insurance PDF Extractor")
st.title("📄 Insurance Document Extractor")

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file is not None:
    st.info("Extracting text from PDF...")
    pages = extract_text_by_page(uploaded_file)
    full_text = "\n".join(p[1] for p in pages)

    st.success("Sending to GPT...")
    fields_output = extract_fields_from_text(full_text)
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