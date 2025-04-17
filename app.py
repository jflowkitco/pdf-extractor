import streamlit as st
import pdfplumber
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI
from dotenv import load_dotenv

# Load .env and set API key
from openai import OpenAI
client = OpenAI()

def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_fields_from_text(text):
    prompt = f"""
    Extract the following details from this insurance document:
    - Insured Name
    - Effective Date
    - Premium
    - Taxes
    - Fees
    - Policy Number
    - Carrier Name
    - Broker Name

    Return the results in this format:
    Insured Name: ...
    Effective Date: ...
    Premium: ...
    Taxes: ...
    Fees: ...
    Policy Number: ...
    Carrier Name: ...
    Broker Name: ...

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
    data = {}
    for line in text_output.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
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
