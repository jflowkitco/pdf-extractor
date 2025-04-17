import pdfplumber
import openai
import pandas as pd
import os
from dotenv import load_dotenv

# Load API key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
print("🔑 API Key Loaded:", openai.api_key[:8], "...")

def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
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

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response['choices'][0]['message']['content']

def save_to_csv(data_text, output_path="extracted_data.csv"):
    lines = data_text.strip().split("\n")
    data = {}
    for line in lines:
        if ':' in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    df = pd.DataFrame([data])
    df.to_csv(output_path, index=False)
    print(f"✅ Data saved to {output_path}")

if __name__ == "__main__":
    pdf_path = "sample.pdf"
    text = extract_text_from_pdf(pdf_path)
    extracted = extract_fields_from_text(text)
    print("📄 Extracted info:\n", extracted)
    save_to_csv(extracted)
